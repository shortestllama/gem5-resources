/* SPDX-License-Identifier: BSD-3-Clause */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "desc_gpu_abi.h"
#include <gem5/m5ops.h>
static unsigned char sq[4096] __attribute__((aligned(4096)));
static unsigned char cq[4096] __attribute__((aligned(4096)));
static unsigned long call(unsigned fid, uintptr_t p, uintptr_t q) {
    register unsigned long a0 asm("a0")=p, a1 asm("a1")=q;
    register unsigned long a7 asm("a7")=3010+fid;
    asm volatile("ecall" : "+r"(a0) : "r"(a1),"r"(a7) : "memory");
    return a0;
}
#define CHECK(fid,p,q) do { unsigned long rc=call(fid,(uintptr_t)(p),(uintptr_t)(q)); \
 if(rc) { printf("AMD_SQUARE_ENCLAVE_FAIL fid=%u rc=%lu\n",fid,rc); return 1; } } while(0)
int main(void) {
    struct desc_gpu_gei_handle h;
    struct desc_gpu_create_request create={.device_id=DESC_GPU_DEVICE_ID,.proposed_slot=0};
    /* Enclave CREATE/full EPM measurement completed before main(). */
    m5_work_begin(0,0);
    CHECK(0,&create,&h);
    for(unsigned i=0;i<2;++i) {
        struct desc_gpu_memory_region r={.base=(uintptr_t)(i?cq:sq),.size=4096,
            .permissions=i?2:1,.role=i?2:1};
        CHECK(1,&h,&r);
    }
    for(unsigned i=0;i<2;++i) {
        struct desc_gpu_hbm_authorization a={.handle=h,.domain=1,.role=i?4:3,
            .permissions=i?2:1,.reference={.resource_id=0,
                .offset=i?0x150000:0x140000,.size=1024}};
        CHECK(10,&a,0);
    }
    struct desc_gpu_queue_config q={.handle=h,.submission_region=0,
        .completion_region=1,.entries=8,.descriptor_bytes=128,.completion_bytes=64};
    CHECK(2,&q,0);
    struct desc_gpu_execution_limits l={.handle=h,.allowed_operations=1ULL<<5,
                                       .max_work_items=256};
    CHECK(3,&l,0);
    struct desc_gpu_amd_fixed_descriptor d={.abi_major=DESC_GPU_ABI_MAJOR,
        .abi_minor=DESC_GPU_ABI_MINOR,.opcode=5,.descriptor_bytes=128,
        .descriptor_version=1,.sequence=1,.gei_id=h.gei_id,.generation=h.generation,
        .profile=1,.domain=1,.input={0,0,0x140000,1024},.output={0,0,0x150000,1024}};
    memcpy(sq,&d,sizeof(d));
    struct desc_gpu_finalize_request f={.handle=h,.descriptor_count=1};
    CHECK(4,&f,0); CHECK(5,&h,0);
    for(;;) {
        struct desc_gpu_trusted_status s;
        CHECK(6,&h,&s);
        if(s.fault) { puts("AMD_SQUARE_ENCLAVE_FAULT"); return 1; }
        if(s.completion_sequence==1) break;
    }
    puts("ALITE_ENCLAVE_COMPLETION_OBSERVED sequence=1 BEFORE_WORKEND");
    fflush(stdout);
    m5_work_end(0,0);
    puts("ALITE_ENCLAVE_AFTER_WORKEND");
    fflush(stdout);
    puts("AMD_SQUARE_ENCLAVE_AUTHORIZED_COMPLETION_PASS");
    /* No DESTROY: reservation cannot be released until verified drain exists. */
    return 0;
}

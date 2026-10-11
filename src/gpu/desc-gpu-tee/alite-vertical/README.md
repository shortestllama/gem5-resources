# A-lite AMD vertical slice (NOT simulated yet)

Actual DESC enclave/SM authorization feeds TrustedGpuControl and the new
AmdProtectedGpu backend's exclusive DsmState. RUN launches one frozen Square
profile; no Python harness creates or finalizes a GEI. Square fixtures are
functionally provisioned only after ownership and finalization. Native VMID 1
and queue 0 are fixed routing constants, not trusted identity.

Both actual artifact bytes are SHA-256 checked against the digests serialized
by the measured Square profile, before any GPU provisioning/doorbell. The image
hash covers its descriptor; descriptor offset 1472 is fixed, not a parameter.
All HBM physical addresses derive from reservation base plus checked offsets.

Native HSA/CP DMA reads an adapter-owned read-only AQL ring. Its private PIO
storage rejects CPU access and accepts only native HSA read-index / CP signal
writes. This changes queue-service timing versus normal RAM queues; no host or
queue-service performance equivalence is claimed. It does not close other AMD
MMIO/BAR paths or prevent untrusted GPU control from confusing native engines.
GEI/generation/RRID authority comes ONLY from trusted DSM, never those DMA IDs.

TEST HARNESS ONLY: functional loading of code, page tables, kernargs, fixed
input (1.618f+i), output inspection, and completion mirroring into EPM. These
are not Linux-accessible provisioning APIs or modeled protected transfers.
Completion verifies 256 output elements, logs pass, increments DSM completion
and retains ownership. It is NOT full drain; teardown remains unavailable.

Manual preparation (may exceed five minutes; no commands run automatically):

```
bash /home/jfford/gpu-smoke-mi200/alite-vertical/build-gem5.sh
bash /home/jfford/gpu-smoke-mi200/alite-vertical/prepare-guest.sh
bash /home/jfford/gpu-smoke-mi200/alite-vertical/run.sh
```

The last script hard-caps simulation at INT115s/KILL+5s. New firmware is required;
old Phase8 firmware lacks the Square/HBM contract. Preparation writes only a
new firmware directory and disk clone. No prior experiments are modified.
The enclave test calls real SBI CREATE/AUTHORIZE/BIND/FINALIZE/RUN/STATUS and
omits DESTROY because release/drain is unfinished. No Linux GPU driver needed.

Success requires BOTH AMD_PROTECTED_SQUARE_RESULT_PASS in run.log and
AMD_SQUARE_ENCLAVE_AUTHORIZED_COMPLETION_PASS in the serial output, normal
m5 exit, plus nonzero application GPU instructions/wavefronts in stats.txt and
one application kernel in gpu-kernels.log. A boot timeout is not a GPU pass.
No real execution, firmware integration, or timing conclusion has been tested.

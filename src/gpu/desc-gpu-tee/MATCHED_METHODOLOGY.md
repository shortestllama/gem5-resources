# Matched unsecured/protected GPU execution comparison

Status: V6 is the current completed evaluation; all 108 cases, adversarial validation,
strict processing, accounting, figures and historical comparison passed.
V5 raw evidence and its images/binaries are immutable historical evidence. Do not
pool V5 samples with V6. The prior READY-TO-COMMIT inventory describes V5, not
these subsequent source changes.

## Question and estimand

What CPU-cycle cost does protected DESC GPU execution add, relative to equivalent
ordinary GPU execution on this **synthetic accelerator**, starting with resident,
cacheable application buffers and an open device? Report total lifecycle and
execution-only costs separately. Fixed-capacity buffer clearing is not added to the measured denominator to dilute
small-workload overhead. No estimate of absolute physical GPU performance
or of the minimum possible hardware-only security cost is implied.

The comparison retains actual protected GEI creation, ownership/range validation,
queue binding, limits, canonical policy/descriptor measurement and finalization,
IOPMP programming, run/stop, trusted status, generation/identity checks, revocation
and teardown. There is no trusted-mode bypass, weakened SM check, GPU timing
change, or attestation-format change. The new benchmark calls production GPU SBI
functions directly; the ordinary backend uses only untrusted Linux and PCI BAR
operations. Shared local validation replaces the two different high-level paths.

## Audit of V5 and correction

| Component | V5 unsecured | V5 protected | V6 matching / classification |
|---|---|---|---|
| Process/memory provisioning | Normal process, static application arrays; extra DMA buffers allocated inside each measured submission | Enclave process/EPM allocation excluded; static EPM buffers directly used for DMA | Same binary, resident 256-KiB cacheable arena per case. Normal DMA mmap or static enclave EPM provisioned outside timed lifecycle. Allocator/process-launch costs excluded explicitly; no per-command bounce allocation |
| Data movement | copy_from_user into coherent DMA allocations and copy_to_user output, plus output memset | Direct DMA to enclave input/output buffers | Direct DMA to application-visible buffers in both; identical initial pattern over all 64-KiB inputs; no bounce copies |
| Layout and cacheability | Workload-sized kernel allocations; kernel-owned rings from module probe | 64-KiB operand arrays and page-sized queues | Same 64-KiB alignment, offsets, region capacities; cacheable coherent ordinary mapping required and checked; same memset loops for queues and output |
| Timing boundaries | Open/close timed; allocation, copying, launch/wait/free mostly hidden in execution; queues persist | Open, info, slot allocation and GEI create timed; close via destructor outside total; queue/output memset outside total | Session open/provisioning common outside; dup/info/slot allocation and close/free common inside. Queue/output memset outside both measured intervals, preserving V5 protected boundaries; validation and printing outside. All protected security lifecycle calls timed |
| Context and queues | Slot 0, persistent rings/monotonic sequence across cases | Allocated slot 1+, fresh GEI/ring every repetition | Same allocator and slot pool (1+), fresh/reset context each repetition, same 16-entry queues, sequence starts at 1 |
| Descriptors | Kernel loop, workload request translations, different unused length/dimension fields | SDK application loop, authorized physical addresses and GEI/generation | One shared descriptor routine and application loop, same zeroed fields/flags/sequence/shape. Only protected identity/generation and actual DMA addresses differ |
| Permissions and limits | No monitor ownership, measurement, or policy installation | Real authorization, bounds, execution limits, finalized canonical measurement | Kept in protected timing; no fake equivalent hashing or policy work charged to baseline |
| Submit | Single legacy ioctl contains almost everything and a mutex spans allocation through wait | Separate SBI run plus scheduler notify ioctl | Same notify ioctl and doorbell count, same short mutex scope. Protected SBI run vs ordinary BAR enable is the authority difference |
| Waiting | Completion-tail polling plus wait_for_completion_timeout(...,1), using jiffy granularity and IRQ reinitialization | Trusted status followed by SDK IRQ wait and recheck | Same bounded active polling loop and rdcycle timeout in both; interrupts masked before measurements in both. No sleep, jiffy threshold, notification race, or timed clock_gettime syscall |
| Completion/consume | Kernel reads CQ and advances head | Trusted status, identity validation, CQ read, consume ioctl per command | Shared CQ validation and per-command consume ioctl. Protected progress read must use SM/DSM; ordinary progress uses a short status ioctl reading normal BAR registers |
| Cleanup | Free coherent payload buffers inside ioctl; rings persist | Stop, revoke IOPMP, scrub device state, destroy, free slot | Both quiesce/reset/release fresh context and close dup FD inside timing; arena lifetime per case. Protected revocation/scrub/generation retirement remain additional required work |
| Device/configuration | Synthetic serial device; IOPMP bypass | Same timing; enforced DMA and descriptor policy | Unchanged, identical CPU/cache/memory/topology/timing settings; only security authority differs |

V5 large single-command COPY/VADD ratios cannot be interpreted as isolated
security overhead. The approximately 8-KiB jump is consistent with the baseline's
allocation/cache/copy and jiffy-wait paths; code inspection does **not** prove a
unique cause. V6 removes the size-dependent allocation/copy path and jiffy waiting
entirely. Active polling is a controlled latency policy, not an energy-efficient
or universally preferable application runtime. Both modes pay for polling, and
poll counts are recorded rather than normalized away.

## Implementation and memory contract

`gpu-matched-benchmark` is a separate executable; the V5 benchmark and archived
binary remain available. Both modes use the same new executable. The shared
arena contains page-aligned SQ/CQ and three 64-KiB operands at fixed offsets.
One batch repeats the same descriptor shape and buffers, as in V5. Each case
uses one warmup and five measured repetitions, each with a fresh context/GEI.

The ordinary driver mmap allocates one fixed 256-KiB coherent arena per open file.
It refuses noncoherent DMA devices, nonshared/executable mappings, wrong lengths
or offsets, misaligned DMA bases, and any DMA mmap conversion to uncached page
attributes. The evaluated RISC-V PCI DT declares `dma-coherent`, and the gem5
I/O path is cache coherent. The arena remains owned by the file/VMA; shared dup
FDs give both modes identical measured dup/GET_INFO/ALLOC/FREE/close operations.

Normal BAR controls only bind the calling file's arena to its allocated context;
no arbitrary user DMA address is accepted for binding. They never touch trusted
DSM/IOPMP MMIO. Busy reset is rejected. Queue writes/reset are checked for being
ignored by a protected locked slot. A bound arena cannot be freed before reset;
abnormal process exit quarantines arena/slots instead of recycling live DMA
memory. This is a test transport for the local platform, not a portable driver API.

## What necessarily remains different

- Enclave execution and intercepted syscalls versus normal process execution;
  SM entry/exit, caller validation and isolation bookkeeping are real DESC costs.
- Protected memory authorization/translation, measured policy and immutable batch
  installation versus ordinary known DMA offsets and BAR queue configuration.
- GEI identity/generation, IOPMP policy/RRID enforcement, DSM lifecycle and exact
  descriptor enforcement versus an unprotected context.
- Trusted SM/DSM status versus ordinary Linux/MMIO progress, then common CQ record
  checks. Reading untrusted CQ/interrupt hints alone would remove required security.
- Protected stop/revocation/device-state scrub and authority retirement versus
  ordinary idle verification/reset. No security cleanup is moved outside timing.

These are required **for this implementation**, not architectural lower bounds.
A remaining status ioctl-versus-SBI instruction-count difference is a backend
transport choice as well as an authority-boundary cost; it cannot honestly be
called pure hardware overhead. Normal DMA pages and EPM use different physical
placements/page tables/allocators, although size, alignment, cacheability and
application access patterns match. Resulting cache/DRAM locality and different
poll counts are residual experimental effects, not intrinsically security costs.
Do not subtract or fabricate cycles to make the protected result slower. If the
advisor needs causal separation of these residuals, add matched-transport,
placement/replication, or other focused ablations.

The estimand excludes provisioned memory, device probe, process/enclave creation,
initial input setup and identical per-repetition queue/output initialization, final correctness checks, and session unmap/close for both.
This is **not** an end-to-end application cost or a claim that enclave creation is
free. Gem5 case-level statistics include provisioning/launch and all six runs;
the application-cycle columns do not. Protected finalize/attestation binding is
included; an explicit report/signature export remains a separate operation.

## Validation and planned comparison

Local checks cover byte-equivalent ordinary/protected descriptors except identity,
completion authority/identity/sequence failures, layout/ELF bounds, actual driver
BAR adapter with owned-slot/locked-write/busy-reset injection, existing security
fixtures, cross-builds and strict parsing. Kernel builds compile the real mmap
path; full-system mmap/cacheability/lifecycle validation passed in both V6 modes.
The new campaign must emit `DESC_GPU_MATCHED_V6_ZERO_COPY_POLLING` in every case
and exactly six `MATCHED_POLLS` rows. Processing rejects legacy or incomplete logs.

Use `compare-matched.py --v5 OLD --matched NEW --output FRESH_OUTPUT` only after
strict processing. It reports old/new ratios at the largest single-command
COPY/VADD sizes, every remaining protected-faster COPY/VADD case, and unsecured
4096→8192-byte COPY and 1024→2048-element VADD step ratios. Review sample variance,
execution cycles, device ticks and poll counts before explaining a residual jump.
V6 observed no protected-faster COPY/VADD cases. Largest batch-1 ratios changed
0.378→2.060 (COPY) and 0.352→3.934 (VADD). The unsecured threshold ratios fell
13.846→1.412 and 12.252→1.222, respectively. This supports the confound diagnosis,
not a unique cause without single-variable ablations. Three unsecured cells have
CV >5%: COPY 256/batch16 (73.2%), VADD 4096/batch16 (13.0%), and VADD
8192/batch1 (43.3%); all samples are retained. See the current advisor tables
and closeout-v6 for the complete numerical review and verification inventory.

## Runtime and approval

V5's per-case `hostSeconds` totals were 19,321 s protected (5.37 h) and 262 s
unsecured, excluding boots. Budget **about 7 hours (roughly 6–9 hours)** for
adversarial validation and two corrected boots on the same server; the new poll
policy and workload layout can change runtime. Earlier two-hour estimates were
not evidence-based. No new full-system run is started automatically. Obtain user
approval and use tmux; exact prepared commands are recorded in the artifact handoff.

Completed campaign wall time: 6 h 47 min (2026-09-15 23:51:50 to
2026-09-16 06:38:49 UTC). No additional campaign is required for this closeout.

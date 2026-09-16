# DESC GPU TEE Phase 8 artifact

**Current revision:** V5 results remain preserved; the matched V6 comparison is
complete and is the primary evaluation (108/108 cases, all campaign gates PASS). See
[MATCHED_METHODOLOGY.md](MATCHED_METHODOLOGY.md) for the audit and protocol.
Use `prepare-image.py --matched` and `experiments.py --matched` for V6.
Current closeout/inventory: `/home/jfford/phase8-artifacts/closeout-v6/`.
Original V5 closeout and results remain historical evidence.


This artifact evaluates the local DESC/gem5 research prototype. It does not
predict NVIDIA, AMD, or other physical GPU performance. V5 full-system adversarial
validation and all 108 performance cases passed. The implementation/evaluation
milestone is complete; paper interpretation and additional experiments remain
subject to advisor review.

## Timing and measurement contract

Both modes use the same accelerator service-time equation:

```
COPY = compute_latency + bytes * copy_byte_latency
VADD = compute_latency + elements * vadd_element_latency
GEMM = compute_latency + m * n * k * gemm_mac_latency
```

Defaults are 100 ns launch and 1 ns per byte/element/MAC. All four parameters
are configurable on `riscv-desc-gpu-tee.py`. Integer overflow faults instead of
wrapping the event time. DMA latency is supplied separately by gem5 memory.
This is a serial synthetic accelerator, with neither a physical GPU pipeline
nor a calibrated throughput/occupancy model. DSM checks and IOPMP lookup have
no additional modeled device latency; their activity is counted. Scrubbing is
an immediate modeled state transition, not a modeled physical SRAM bandwidth.
Stop returns BUSY while active; there is no forced-abort or mid-DMA buffer reuse.

The experiment generator uses one configuration for both modes: two 3 GHz
TimingSimpleCPU cores, private 16 KiB L1I/L1D and 256 KiB L2, dual-channel
DDR4-2400, 3 GiB memory, and 17 PMP entries per hart. Both instantiate trusted
MMIO devices. Only unsecured accelerator DMA bypasses IOPMP. Never run protected
workloads using `--security-mode unsecured`.

COPY sizes double from 64 to 65536 bytes; VADD doubles from 16 to 16384 elements;
square GEMM uses 2, 4, 8, 16, 32. Each uses batches 1 and 16, one warmup and five
measured repetitions: 108 cases in two boots, 648 samples (540 measured). A batch submits all descriptors
with one notification in both modes. Each protected repetition creates a fresh
GEI; the enclave process stays alive for the six repetitions. Each batch repeats
the same command over the same buffers; each case starts a new process. Cases
run in fixed order with persistent caches; resetting counters does not flush them.

`PHASE8_CSV` records in-enclave/normal-process `rdcycle` measurements of total,
create, configuration/preparation, finalization, launch, execution/consume,
stop and destroy. In current matched V6, resident arena provisioning, session open,
process/enclave creation, input initialization, common queue/output zeroing and
final correctness checks are outside these intervals. Both modes use zero-copy
cacheable arenas and the same active polling loop; protected SM authorization,
measurement, policy installation and revocation remain inside timing. Status
transport (ioctl versus SBI), enclave execution, page tables/physical placement
and poll cadence still differ. This is provisioned implementation overhead,
not an isolated hardware security-gate cost. Historical V5 used an unsecured
allocation/copy/jiffy-wait path and must not be pooled with V6.

The ABI's historical `device_cycles` field actually contains **simulation
ticks**, from descriptor fetch to result DMA completion, excluding completion
DMA. CSV correctly names this `device_ticks`. `gpu.serviceTicks` includes
completion DMA; `gpu.computeTicks` is synthetic compute time. DMA byte counts
include descriptors and completions. IOPMP counters count logical authorized
or rejected requests, not memory-system packet fragments. Convert ticks using
`simFreq`; do not interpret ticks as CPU cycles.

`stats.txt` is reset after module loading and dumped after each case. Its ROI
includes process/enclave launch, warmup, all five measured repetitions,
preparation, and result verification. CSV scaling statistics exclude warmup. Do not mislabel the
aggregate CPU/cache/DRAM statistics as measured-only per-operation samples.
Attestation is measured separately by `gpu-attestation-export` and is excluded
from the scaling benchmark.

## Build and bounded validation

From `/home/jfford`:

```sh
sh desc/tests/gpu-tee-phase8/build-local.sh /tmp/desc-phase8-build
cd /home/jfford/gem5
scons -j4 build/RISCV/gem5.opt \
  build/RISCV/dev/gpu_tee/desc_gpu_abi.test.opt \
  build/RISCV/dev/gpu_tee/gpu_compute.test.opt \
  build/RISCV/dev/gpu_tee/gpu_timing.test.opt \
  build/RISCV/dev/gpu_tee/desc_gpu_dsm.test.opt \
  build/RISCV/dev/gpu_tee/desc_iopmp.test.opt
cd /home/jfford
python3 desc/tests/gpu-tee-phase8/run-validation.py --output /tmp/desc-phase8-validation
python3 gem5-resources/src/gpu/desc-gpu-tee/test-processing.py
```

Expected: `DESC_GPU_PHASE8_GUEST_BUILD_PASS`,
`DESC_GPU_PHASE8_LOCAL_PASS`, `DESC_GPU_PHASE8_PROCESSING_TEST_PASS`.
The build script reads the existing toolchain/kernel build and writes all
module/application outputs under its output directory. It does not modify DESC's `gsr` artifacts. Use
`sh desc/tests/gpu-tee-phase8/build-firmware.sh` to build the repaired ROM and SM
into a separate directory.

## Completed V5 evidence and reproduction

Authoritative preserved data:

- `/home/jfford/phase8-artifacts/adversarial-v5/board.platform.terminal`
- `/home/jfford/phase8-artifacts/experiments-batched-v5/{unsecured,protected}/`
- `/home/jfford/phase8-artifacts/experiments-batched-v5/manifest.json`
- `/home/jfford/phase8-artifacts/closeout/validation-verified/adversarial-results.csv`
- `/home/jfford/phase8-artifacts/attestation-repaired/board.platform.terminal`

V5 guest markers: `DESC_GPU_PHASE8_GUEST_ADVERSARIAL_PASS`,
`DESC_GPU_PHASE8_MODE_PASS_unsecured`, `DESC_GPU_PHASE8_MODE_PASS_protected`.
Legacy compatibility also passed `DESC_GPU_PHASE2_PASS` in
`baseline-regression-repaired/`. Offline processing:

```sh
python3 process-results.py /home/jfford/phase8-artifacts/experiments-batched-v5
```

Expected: `DESC_GPU_PHASE8_RESULTS_PASS`. This writes `operation-scaling.csv`,
`lifecycle-amortization.csv`, `samples.csv`, `gem5-statistics.csv` and per-case
platform JSONs. The processor checks boundaries/order, per-case PASS, all six
repetitions, DMA accounting, platform parity and complete per-case statistic dumps;
one optional automatic final dump is excluded. The closeout independently
reprocessed to a separate directory and reproduced the original CSVs exactly.

`summarize-results.py DIRECTORY --output OUTPUT` additionally verifies actual
compute/DMA/IOPMP/teardown accounting and produces tables and PNG/PDF figures.
It requires matplotlib (the closeout used 3.11.2); it never runs simulations.
Generated advisor material is in `/home/jfford/phase8-artifacts/advisor-meeting/`.

To reproduce elsewhere, build guest/firmware, run `prepare-image.py --source
BASE.ext2 --output NEW.ext2 --build BUILD`, then `experiments.py --kernel FW.elf
--bootrom ROM.elf --disk-image NEW.ext2 --output NEW_DIRECTORY`.
Packaging verifies inserted files byte-for-byte. The manifest records input
binary and relevant source hashes, including untracked files. New campaigns use
two boots with one reset/dump pair per case. Do not pool older fresh-boot-per-case
or failed V4 results with V5. Existing images/campaign directories are not replaced.

Additional long simulations require user approval. **Expect several hours**,
not a guaranteed two-hour run; use tmux and announce the estimate before starting.
The generated `run.sh` saves simulator output in `unsecured.log`/`protected.log`;
watch each mode's `board.platform.terminal` for case progress. It skips completed
modes but refuses to overwrite incomplete mode output. Preserve an incomplete
mode directory and its `.log` before retrying; there is no within-boot resume.

## Adversarial evidence and limits

| Property | Evidence |
| --- | --- |
| Forged SBI handles, caller identity, cross-enclave ownership, stale reuse | Actual SM C code with mocked current-thread/MMIO platform |
| EPM containment, zero/overflow/cross-enclave ranges | Actual SM host tests |
| Stop, revocation, teardown failure retains metadata/generation; isolation during cleanup | Actual SM failure-injection tests plus IOPMP lock/revocation model tests |
| Finalized multi-GEI placement/order invariance, append-only evidence, policy/descriptor mutation sensitivity | Actual SM hashing/finalization code and SHA3 |
| Cross-slot handles, replay, queue overflow, residual queue/policy state, sticky faults | Actual DSM unit tests |
| Unauthorized and cross-RRID DMA, permissions, partial hits, revocation/reset | Actual IOPMP unit tests |
| Forged/suppressed interrupts never establish completion authority | Actual SDK wait logic with mocked SBI/ioctl; guest suppression fixture |
| S-mode SBI rejection, denied trusted MMIO reads/writes, immutable BAR state, protected reset attempts | Test-only guest kernel module; V5 full-system PASS |
| Descriptor mutation and fault/ordinary automatic cleanup with reuse | Retained Phase 5 guest regression |
| Device → SM → enclave signatures, wrong challenge and signed-field tampering | Production C signer and independent Python Edwards25519/SHA3-512 verifier |

`run-validation.py` writes `adversarial-results.csv`, distinguishing model,
mocked-platform, and guest evidence. Guest rows remain PENDING until supplied
with `--guest-log .../board.platform.terminal`. Host tests are not a
substitute for CPU PMP enforcement, SMP integration, or successful guest runs.
Protected MMIO reset is rejected; a fresh model reset has no residual authority.
No new external reset/abort interface, security-control backdoor, certificate
hierarchy, side-channel claim, or physical-attack claim is introduced.

## Live attestation verification

Run `/root/gpu-attestation-export NONCE_HEX` through `desc-runner -e 32M` in the
secured guest, with a verifier-generated 32-byte nonce (64 hex digits). It
exports a GPU-bound report and `DESC_GPU_PHASE8_ATTESTATION_CYCLES`. Offline:

```sh
python3 /home/jfford/desc/tests/gpu-tee-phase8/verify-report.py GUEST_LOG \
  --root DEVICE_ROOT_HEX --sm-hash EXPECTED_SM_HASH_HEX \
  --enclave-hash EXPECTED_GPU_BOUND_HASH_HEX --challenge NONCE_HEX
```

Expected: `DESC_GPU_PHASE8_SIGNATURE_CHAIN_PASS`. The root and expected hashes
must come from a trusted verifier policy, not be trusted merely because they
appear in the report. The measured enclave includes initialized launch-stack
contents, so expected measurements must match the launch arguments. This
prototype uses its existing test device root and Edwards25519 with SHA3-512,
not standard SHA-512 Ed25519. No new signing hierarchy is added. Unsigned report
padding is not evidence and is not authenticated by the existing format.

## Repairs covered by validation

The existing measured boot chain is initialized through the read-only boot ROM.
ROM fixes preserve the DTB, synchronize secondary harts, use complete key/hash
lengths and erase the full device secret. SM reports are zero-initialized and
missing boot evidence is rejected. Live root/SM/nonce/signature checks passed;
`--chain-only` does not approve an enclave/GPU allowlist policy.

The test-only adversary uses the normal-world DESC SBI extension and `_IOW`
requests so the SM forwards its slot argument correctly. The benchmark uses a
64-KiB maximum ELF page size to avoid a trailing BSS-only segment incompatible
with DESC's existing loader. SDK wait retries stale successful IRQ hints within
one timeout budget, while trusted status and completion identity remain required.
These repairs have focused host tests and completed V5 guest coverage.

The model is serial and synthetic. IOPMP/DSM checks and local scrubbing have no
additional hardware latency. CPU-side costs use a debug SM build. Large single
COPY/VADD batches can appear faster protected due to the different software
paths; that is not an isolated security speedup. Five in-boot repetitions exhibit
some high variance and are not independent boot replications. The single earlier
attestation timing is not a repeated performance benchmark. Advisor-requested
baseline matching, sensitivity sweeps, replication and presentation changes are
subsequent evaluation refinements.

## Current matched V6 evidence (2026-09-16)

Raw results: `/home/jfford/phase8-artifacts/experiments-matched-v6/`.
Final marker: `DESC_GPU_MATCHED_V6_ALL_PASS`; 108 cases, 648 samples,
540 measured samples, 5,508 commands including warmups. Identical synthetic
parameters and CPU/cache/memory topology apply to both modes. See
[MATCHED_METHODOLOGY.md](MATCHED_METHODOLOGY.md) for exact timing boundaries,
security costs retained, transport/placement residuals and interpretation limits.

Current advisor notes/plots: `phase8-artifacts/advisor-meeting/`; original V5
material: `phase8-artifacts/advisor-meeting-v5/`. Do not pool protocols or replace
raw evidence. Reprocess a scratch copy/link view to preserve existing derived data:

```sh
python3 process-results.py /path/to/scratch-campaign
python3 summarize-results.py /path/to/scratch-campaign --output /path/to/new-figures
python3 compare-matched.py --v5 /home/jfford/phase8-artifacts/experiments-batched-v5 --matched /path/to/scratch-campaign --output /path/to/new-comparison
```

The scratch campaign needs a copy of `manifest.json` and links to the original
`unsecured/` and `protected/` directories. Plotting requires matplotlib (the
recorded local environment is `phase8-artifacts/closeout/plot-env/bin/python`).
The raw manifest records evaluated source/input/tool hashes; later documentation
edits do not rewrite that manifest. Commit scope is recorded separately in
`closeout-v6/intentional-files.json`. A rerun requires a fresh result directory
and prior user approval; the completed campaign took 6 h 47 min. No rerun is
needed merely to regenerate tables or plots.

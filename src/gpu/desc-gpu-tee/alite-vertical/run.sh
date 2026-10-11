#!/bin/bash
set -euo pipefail
base=/home/jfford/gpu-smoke-mi200/alite-vertical
# Require NEW firmware containing the Square/HBM contract and a SEPARATE disk
# containing /root/amd-square-enclave plus existing DESC runtime/driver.
ALITE_FW=${ALITE_FW:-$base/firmware-matched-kernel/sm/platform/generic/firmware/fw_payload.elf}
ALITE_DISK=${ALITE_DISK:-$base/rootfs.ext2}
ALITE_BOOTROM=${ALITE_BOOTROM:-$base/firmware-matched-kernel/bootrom/bootrom.elf}
for file in "$ALITE_FW" "$ALITE_DISK" "$ALITE_BOOTROM"; do test -f "$file"; done
ALITE_OUT=${ALITE_OUT:-$base/output}
ALITE_LOG=${ALITE_LOG:-$base/run.log}
if [ -e "$ALITE_OUT" ] || [ -e "$ALITE_LOG" ]; then
 echo "Choose fresh ALITE_OUT and ALITE_LOG paths; preserving existing results" >&2
 exit 1
fi
timeout --signal=INT --kill-after=5s 115s \
 /home/jfford/gem5/build/ALITE_AMD/gem5.opt -d "$ALITE_OUT" \
 --debug-flags=GPUKernelInfo --debug-file=gpu-kernels.log "$base/config.py" \
 --kernel "$ALITE_FW" --bootrom "$ALITE_BOOTROM" --disk-image "$ALITE_DISK" \
 --readfile "$base/readfile.sh" --cpu-type timing > "$ALITE_LOG" 2>&1

grep -q AMD_PROTECTED_SQUARE_RESULT_PASS "$ALITE_LOG"
grep -q AMD_SQUARE_ENCLAVE_AUTHORIZED_COMPLETION_PASS "$ALITE_OUT/board.platform.terminal"

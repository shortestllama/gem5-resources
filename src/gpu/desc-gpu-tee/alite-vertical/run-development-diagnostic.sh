#!/bin/bash
# MANUAL ONLY. Development EPM=2 MiB; binary/measurement/security unchanged.
# No timeout; original run-accelerated.sh/readfile.sh retain EPM=32 MiB.
set -euo pipefail
base=/home/jfford/gpu-smoke-mi200/alite-vertical
out=${ALITE_OUT:-$base/output-development-diag1}
log=${ALITE_LOG:-$base/run-development-diag1.log}
test ! -e "$out"
test ! -e "$log"
for artifact in "$base/rootfs-termination.ext2" "$base/firmware-matched-kernel/bootrom/bootrom.elf" "$base/firmware-matched-kernel/sm/platform/generic/firmware/fw_payload.elf"; do test -f "$artifact"; done
set +e
PYTHONUNBUFFERED=1 /home/jfford/gem5/build/ALITE_AMD/gem5.opt -d "$out" \
 --debug-flags=GPUKernelInfo --debug-file=gpu-diagnostic.log "$base/config.py" \
 --kernel "$base/firmware-matched-kernel/sm/platform/generic/firmware/fw_payload.elf" \
 --bootrom "$base/firmware-matched-kernel/bootrom/bootrom.elf" \
 --disk-image "$base/rootfs-termination.ext2" --readfile "$base/readfile-development.sh" \
 --cpu-type atomic-timing --gpu-diagnostics > "$log" 2>&1

status=$?
set -e
printf "ALITE_GEM5_PROCESS_EXIT_STATUS=%s\n" "$status" | tee -a "$log"
printf "%s\n" "$status" > "${log}.exit-status"
exit "$status"

#!/bin/bash
# MANUAL ONLY: no wall-clock timeout; Ctrl-C remains available.
set -euo pipefail
base=/home/jfford/gpu-smoke-mi200/alite-vertical
out=${ALITE_OUT:-$base/output-atomic-roi1}
log=${ALITE_LOG:-$base/run-atomic-roi1.log}
test ! -e "$out"
test ! -e "$log"
for artifact in "$base/rootfs-roi.ext2" "$base/firmware-matched-kernel/bootrom/bootrom.elf" "$base/firmware-matched-kernel/sm/platform/generic/firmware/fw_payload.elf"; do test -f "$artifact"; done
exec /home/jfford/gem5/build/ALITE_AMD/gem5.opt -d "$out" \
 --debug-flags=GPUKernelInfo --debug-file=gpu-kernels.log "$base/config.py" \
 --kernel "$base/firmware-matched-kernel/sm/platform/generic/firmware/fw_payload.elf" \
 --bootrom "$base/firmware-matched-kernel/bootrom/bootrom.elf" \
 --disk-image "$base/rootfs-roi.ext2" --readfile "$base/readfile.sh" \
 --cpu-type atomic-timing > "$log" 2>&1

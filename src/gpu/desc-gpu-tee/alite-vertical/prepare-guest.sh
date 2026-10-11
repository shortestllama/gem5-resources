#!/bin/bash
set -euo pipefail
# MANUAL ONLY: firmware compilation and disk copying may exceed five minutes.
base=/home/jfford/gpu-smoke-mi200/alite-vertical
export TOOLCHAIN=/home/jfford/desc-before-update/gsr/riscv64/bin/riscv64-unknown-elf-
bash "$base/repackage-firmware.sh"
/home/jfford/desc-before-update/gsr/riscv64/bin/riscv64-unknown-linux-gnu-gcc \
 -O2 -Wall -Wextra -Werror -static -I/home/jfford/desc/src/common -I/home/jfford/gem5/include \
 "$base/square-enclave.c" /home/jfford/gem5/util/m5/src/abi/riscv/m5op.S -Wl,-z,max-page-size=65536 -o "$base/amd-square-enclave"
# Preserve every existing disk and experiment. Only a new clone is written.
if [ -e "$base/rootfs.ext2" ]; then
 echo "Refusing to overwrite existing vertical-test disk" >&2; exit 1
fi
cp --reflink=auto /home/jfford/phase8-artifacts/rootfs-final-batched-policy-v2.ext2 \
 "$base/rootfs.ext2"
debugfs -w -R "write $base/amd-square-enclave /root/amd-square-enclave" "$base/rootfs.ext2"
echo "Prepared isolated firmware and guest; inspect debugfs output for errors."

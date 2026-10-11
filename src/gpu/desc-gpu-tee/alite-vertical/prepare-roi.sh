#!/bin/bash
set -euo pipefail
base=/home/jfford/gpu-smoke-mi200/alite-vertical
test ! -e "$base/rootfs-roi.ext2"
/home/jfford/desc-before-update/gsr/riscv64/bin/riscv64-unknown-linux-gnu-gcc \
 -O2 -Wall -Wextra -Werror -static -I/home/jfford/desc/src/common -I/home/jfford/gem5/include \
 "$base/square-enclave.c" /home/jfford/gem5/util/m5/src/abi/riscv/m5op.S \
 -Wl,-z,max-page-size=65536 -o "$base/amd-square-enclave-roi"
cp --reflink=auto "$base/rootfs.ext2" "$base/rootfs-roi.ext2"
debugfs -w -R 'rm /root/amd-square-enclave' "$base/rootfs-roi.ext2"
debugfs -w -R "write $base/amd-square-enclave-roi /root/amd-square-enclave" "$base/rootfs-roi.ext2"
python3 - <<'PY_VERIFY'
from pathlib import Path
import subprocess
base=Path('/home/jfford/gpu-smoke-mi200/alite-vertical')
r=subprocess.run(['debugfs','-R','cat /root/amd-square-enclave',str(base/'rootfs-roi.ext2')],capture_output=True,check=True)
assert r.stdout == (base/'amd-square-enclave-roi').read_bytes()
assert '-e 32M' in (base/'readfile.sh').read_text()
print('PASS: ROI guest staged exactly; full 32 MiB EPM retained')
PY_VERIFY

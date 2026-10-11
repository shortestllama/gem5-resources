#!/bin/bash
set -euo pipefail
# MANUAL ONLY. Reuse validated Linux; rebuild CURRENT SM, preserving old firmware/disk.
base=/home/jfford/gpu-smoke-mi200/alite-vertical
if [ -e "$base/firmware-matched-kernel" ]; then
 echo "Refusing to overwrite firmware-matched-kernel" >&2; exit 1
fi
python3 - <<'PY_KERNEL'
from pathlib import Path
import struct, hashlib
source = Path('/home/jfford/phase8-artifacts/repair-build/sm/platform/generic/firmware/fw_payload.elf')
out = Path('/home/jfford/gpu-smoke-mi200/alite-vertical/known-working-kernel.Image')
b = source.read_bytes()
assert b[:6] == b'\x7fELF\x02\x01'
off = struct.unpack_from('<Q', b, 40)[0]
sz, n, si = struct.unpack_from('<HHH', b, 58)
sh = [struct.unpack_from('<IIQQQQIIQQ', b, off+i*sz) for i in range(n)]
names = b[sh[si][4]:sh[si][4]+sh[si][5]]
sections = [s for s in sh if names[s[0]:].split(b'\0',1)[0] == b'.payload']
assert len(sections) == 1
s = sections[0]
payload = b[s[4]:s[4]+s[5]]
expected = '79ba5edd44a04b8e2900febbcabd867dc325f2548c032f45ccabe69d754bcf99'
assert hashlib.sha256(payload).hexdigest() == expected
assert b'do_execveat_desc' in payload
if out.exists():
 assert out.read_bytes() == payload, 'Existing kernel artifact differs'
else:
 out.write_bytes(payload)
print('Validated known-working kernel payload:', expected)
PY_KERNEL
export TOOLCHAIN=/home/jfford/desc-before-update/gsr/riscv64/bin/riscv64-unknown-elf-
export KERNEL_IMAGE="$base/known-working-kernel.Image"
bash /home/jfford/desc/tests/gpu-tee-phase8/build-firmware.sh "$base/firmware-matched-kernel"
echo 'Current SM rebuilt with matching kernel; existing rootfs retained.'

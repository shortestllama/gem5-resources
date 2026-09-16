#!/usr/bin/env python3
"""Populate a NEW copy of the existing ext2 image; never write the source image."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--matched',action='store_true',help='include matched comparison benchmark')
p.add_argument('--build',type=Path,default=Path('/tmp/desc-phase8-build'))
a=p.parse_args()
if a.output.exists(): p.error('output must not exist')
files={'protected-gpu-eapp':a.build/'protected-gpu-eapp',
       'simplified-gpu-test':a.build/'simplified-gpu-test',
       'gpu-attestation-export':a.build/'gpu-attestation-export',
       'gpu-benchmark':a.build/'gpu-benchmark',
       'simplified-gpu.ko':a.build/'driver/simplified-gpu.ko',
       'desc-gpu-adversary.ko':a.build/'adversary/desc-gpu-adversary.ko'}
if a.matched: files['gpu-matched-benchmark']=a.build/'gpu-matched-benchmark'
for path in files.values():
    if not path.is_file(): p.error(f'missing build artifact {path}')
shutil.copyfile(a.source,a.output)
with tempfile.TemporaryDirectory(prefix='phase8-image-') as tmp:
    for name,source in files.items():
        # Fixed simple names avoid debugfs command-language quoting ambiguity.
        local=Path(tmp)/name; shutil.copyfile(source,local)
        for command in (f'rm /root/{name}',f'write {local} /root/{name}',
                        f'set_inode_field /root/{name} mode 0100755'):
            subprocess.run(['debugfs','-w','-R',command,str(a.output)],check=True,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        extracted=Path(tmp)/('check-'+name)
        subprocess.run(['debugfs','-R',f'dump /root/{name} {extracted}',str(a.output)],check=True,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if extracted.read_bytes()!=source.read_bytes():
            raise SystemExit(f'FAIL image verification {name}')
print('DESC_GPU_PHASE8_IMAGE_PASS')

#!/usr/bin/env python3
"""Generate reproducible Phase 8 commands; never starts long simulations implicitly."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--matched',action='store_true',help='V6 matched cacheable zero-copy and polling protocol')
p.add_argument('--gem5', type=Path, default=Path('/home/jfford/gem5'))
p.add_argument('--desc', type=Path, default=Path('/home/jfford/desc'))
p.add_argument('--kernel', type=Path, required=True)
p.add_argument('--bootrom', type=Path, required=True)
p.add_argument('--disk-image', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
for name, default in [('compute-latency','100ns'),('copy-byte-latency','1ns'),
                      ('vadd-element-latency','1ns'),('gemm-mac-latency','1ns')]:
    p.add_argument('--'+name, default=default)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

cases = [(op,n,batch) for op,sizes in [('copy',[2**i for i in range(6,17)]),
          ('vadd',[2**i for i in range(4,15)]),('gemm',[2,4,8,16,32])]
         for n in sizes for batch in (1,16)]
manifest = {'schema':3 if a.matched else 2, 'protocol':'matched-zero-copy-poll-v6' if a.matched else 'legacy-v5', 'layout':'batched-modes', 'warmups':1, 'repetitions':5, 'cases':cases,
            'timing':{k:v for k,v in vars(a).items() if k.endswith('latency')},
            'platform':{'cpu':'TimingSimpleCPU','cores':2,'clock':'3GHz',
                        'memory':'DualChannelDDR4_2400 3GiB', 'l1i':'16KiB',
                        'l1d':'16KiB','private_l2':'256KiB','pmp_entries':17},
            'inputs':{str(path.resolve()):digest(path) for path in
                      (a.kernel,a.bootrom,a.disk_image,a.gem5/'build/RISCV/gem5.opt')}}
for name,repo in [('desc',a.desc),('gem5',a.gem5)]:
    manifest[name] = {'head':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
                      'diff_sha256':hashlib.sha256(subprocess.check_output(['git','-C',str(repo),'diff','--binary'])).hexdigest()}
manifest['source_files'] = {}
for repo, directories in ((a.desc, ('src/common','src/sdk','src/gpu-eapp','src/linux-simplified-gpu','tests/gpu-tee-phase8')),
                          (a.gem5, ('src/dev/gpu_tee',))):
    for directory in directories:
        for source in sorted((repo/directory).rglob('*')):
            if source.is_file() and (source.suffix in ('.c','.cc','.cpp','.h','.hh','.hpp','.py','.sh','.rcS') or source.name in ('CMakeLists.txt','Makefile')):
                manifest['source_files'][str(source.resolve())] = digest(source)
config=a.gem5/'configs/example/gem5_library/riscv-desc-gpu-tee.py'
manifest['source_files'][str(config.resolve())] = digest(config)
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
commands = ['#!/bin/sh','set -eu']
for mode in ('unsecured','protected'):
    run=(a.output/mode).resolve()
    script=(a.output/(mode+'.rcS')).resolve()
    guest=['#!/bin/sh','set -eu',
           "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then echo DESC_GPU_PHASE8_CAMPAIGN_FAIL; fi' EXIT",
           'insmod /root/keystone-driver.ko','insmod /root/simplified-gpu.ko']
    if a.matched and mode=='unsecured':
        guest += ['/root/simplified-gpu-test']
    for op,n,batch in cases:
        label=f'{mode}-{op}-{n}-{batch}'
        invocation=['/root/gpu-matched-benchmark' if a.matched else '/root/gpu-benchmark',mode,op,str(n),str(batch)]
        if mode=='protected':
            invocation=['/sbin/desc-runner','-e','32M',*invocation]
        guest += [f'echo PHASE8_CASE_BEGIN,{label}', '/sbin/m5 resetstats',
                  shlex.join(invocation), '/sbin/m5 dumpstats',
                  f'echo PHASE8_CASE_END,{label}']
    guest += [f'echo DESC_GPU_PHASE8_MODE_PASS_{mode}', '/sbin/m5 exit']
    script.write_text('\n'.join(guest)+'\n')
    cmd=[str((a.gem5/'build/RISCV/gem5.opt').resolve()),'--outdir='+str(run),
         str(config.resolve()), '--kernel',str(a.kernel.resolve()),
         '--bootrom',str(a.bootrom.resolve()),'--disk-image',str(a.disk_image.resolve()),
         '--cpu-type','timing','--security-mode',mode,'--readfile',str(script)]
    for key,value in manifest['timing'].items():
        cmd += ['--'+key.replace('_','-'),value]
    log=shlex.quote(str(run/'board.platform.terminal'))
    marker=f'DESC_GPU_PHASE8_MODE_PASS_{mode}'
    commands += [f'if grep -q {marker} {log} 2>/dev/null && ! grep -q _FAIL {log}; then',
                 f'  echo "Already complete: {mode}"', 'else',
                 f'  if [ -d {shlex.quote(str(run))} ]; then',
                 f'    echo "Incomplete existing output: {run}; preserve it before retrying." >&2',
                 '    exit 1', '  fi',
                 f'  echo "Starting {mode}; simulator log: {run}.log"',
                 '  '+shlex.join(cmd)+' >'+shlex.quote(str(run)+'.log')+' 2>&1',
                 f'  grep -q {marker} {log}',
                 f'  if grep -q _FAIL {log}; then exit 1; fi',
                 f'  echo "Completed: {mode}"', 'fi']
commands += ['echo DESC_GPU_PHASE8_CAMPAIGN_PASS']
manifest['guest_scripts']={str((a.output/(mode+'.rcS')).resolve()):digest(a.output/(mode+'.rcS')) for mode in ('unsecured','protected')}
manifest['evaluation_tools']={str(path.resolve()):digest(path) for path in Path(__file__).parent.glob('*.py')}
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(a.output/'run.sh').write_text('\n'.join(commands)+'\n')
print(f'PHASE8_EXPERIMENTS_GENERATED cases={len(cases)*2} boots=2 commands={a.output / "run.sh"}')

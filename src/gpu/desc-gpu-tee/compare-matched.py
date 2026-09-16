#!/usr/bin/env python3
"""Compare completed V5 and matched results; never modify either input campaign."""
import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--v5',type=Path,required=True)
p.add_argument('--matched',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
assert json.loads((a.matched/'manifest.json').read_text())['protocol']=='matched-zero-copy-poll-v6'
def read(d):
    with (d/'operation-scaling.csv').open() as f:
        return {(r['operation'],int(r['size']),int(r['batch'])):r for r in csv.DictReader(f)}
old,new=read(a.v5),read(a.matched)
if old.keys()!=new.keys():raise SystemExit('FAIL different case grids')
rows=[]
for key in old:
    before,after=old[key],new[key]
    rows.append(dict(operation=key[0],size=key[1],batch=key[2],
        v5_ratio=float(before['protected_over_unsecured']),matched_ratio=float(after['protected_over_unsecured']),
        v5_unsecured_cycles=float(before['unsecured_cycles']),matched_unsecured_cycles=float(after['unsecured_cycles']),
        v5_protected_cycles=float(before['protected_cycles']),matched_protected_cycles=float(after['protected_cycles'])))
a.output.mkdir(parents=True,exist_ok=False)
with (a.output/'v5-comparison.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=['# Matched comparison against historical V5','',
 'The protocols have different lifecycle transports: matched excludes common queue/output zeroing,',
 'uses cached zero-copy arenas and active polling, and excludes common case provisioning.',
 'Differences are descriptive; this is not a single-variable causal ablation.','',
 '| Operation, batch 1 | V5 unsecured threshold ratio | Matched unsecured threshold ratio |',
 '|---|---:|---:|']
for op,low,high in [('copy',4096,8192),('vadd',1024,2048)]:
    ratios=[float(d[op,high,1]['unsecured_cycles'])/float(d[op,low,1]['unsecured_cycles']) for d in (old,new)]
    lines.append(f'| {op.upper()}, {low} → {high} | {ratios[0]:.3f}× | {ratios[1]:.3f}× |')
lines += ['', 'Threshold ratios quantify the old approximately 8-KiB discontinuity; inspect',
          'sample variability and device ticks before classifying any residual jump.','',
          '| Largest single-command case | V5 protected / unsecured | Matched protected / unsecured |',
          '|---|---:|---:|']
for op,n in [('copy',65536),('vadd',16384)]:
    r=next(r for r in rows if (r['operation'],r['size'],r['batch'])==(op,n,1))
    lines.append(f"| {op.upper()} {n} | {r['v5_ratio']:.3f}× | {r['matched_ratio']:.3f}× |")
faster=[r for r in rows if r['operation'] in ('copy','vadd') and r['batch']==1 and r['matched_ratio']<1]
lines += ['',f'Matched COPY/VADD batch-1 cases with protected mean below unsecured: **{len(faster)}**.',
          'If nonzero, the effect has not disappeared; do not force or relabel it as overhead.',
          'Use matched-polls.csv, execution-cycle and device-tick columns to investigate residual',
          'poll cadence, placement/cache effects and timing noise. No real-GPU prediction is implied.']
(a.output/'v5-comparison.md').write_text('\n'.join(lines)+'\n')
print('DESC_GPU_MATCHED_V5_COMPARISON_PASS')

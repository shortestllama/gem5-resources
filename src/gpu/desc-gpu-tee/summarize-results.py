#!/usr/bin/env python3
"""Audit processed synthetic-accelerator results and export advisor figures/tables.
Run process-results.py first. Requires matplotlib; does not run simulations.
"""
import argparse
import collections
import csv
import json
import math
from pathlib import Path
import statistics

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('directory',type=Path)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
def read(name):
    with (a.directory/name).open() as f: return list(csv.DictReader(f))
def write(name,rows):
    with (a.output/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
manifest=json.loads((a.directory/'manifest.json').read_text())
samples=read('samples.csv'); scaling=read('operation-scaling.csv'); lifecycle=read('lifecycle-amortization.csv')
assert len(samples)==len(manifest['cases'])*2*6
stats=collections.defaultdict(dict)
for r in read('gem5-statistics.csv'):
    stats[r['run']][r['stat']]=float(r['value'])
metrics=[]
prefix='board.platform.simplified_gpu.gpu.'
for mode in ('unsecured','protected'):
    for op,n,batch in manifest['cases']:
        label=f'{mode}-{op}-{n}-{batch}'; d=stats[label]
        config=json.loads((a.directory/(label+'-platform.json')).read_text())
        gpu=config['board']['platform']['simplified_gpu']
        work=n**3 if op=='gemm' else n
        unit={'copy':'copy_byte_latency','vadd':'vadd_element_latency','gemm':'gemm_mac_latency'}[op]
        expected=6*batch*(gpu['compute_latency']+work*gpu[unit])
        assert d[prefix+'commands']==6*batch,label
        assert d[prefix+'computeTicks']==expected,label
        assert d['board.iopmp.iopmp.denied']==0,label
        assert d['board.iopmp.iopmp.authorized']==(6*batch*(4 if op=='copy' else 5) if mode=='protected' else 0),label
        assert d[prefix+'teardowns']==(6 if mode=='protected' else 0),label
        selected=[r for r in samples if (r['mode'],r['operation'],int(r['size']),int(r['batch']))==(mode,op,n,batch)]
        assert len(selected)==6,label
        assert d[prefix+'dmaReadBytes']==sum(int(r['dma_read_bytes']) for r in selected),label
        assert d[prefix+'dmaWriteBytes']==sum(int(r['dma_write_bytes']) for r in selected),label
        metrics.append({'case':label,'commands':d[prefix+'commands'],'compute_ticks':expected,
                        'iopmp_authorized':d['board.iopmp.iopmp.authorized'],
                        'iopmp_denied':0,'dma_read_bytes':d[prefix+'dmaReadBytes'],
                        'dma_write_bytes':d[prefix+'dmaWriteBytes']})
stages=['create_cycles','config_cycles','finalize_cycles','launch_cycles','execution_cycles','stop_cycles','destroy_cycles']
for r in samples:
    assert all(math.isfinite(float(v)) and float(v)>=0 for k,v in r.items() if k not in ('mode','operation'))
    assert sum(int(r[k]) for k in stages)<=int(r['total_cycles'])
write('device-accounting.csv',metrics)
variability=[]
for row in lifecycle:
    values=[int(r['total_cycles']) for r in samples if all(r[k]==row[k] for k in ('mode','operation','size','batch')) and int(r['repetition'])>0]
    variability.append({k:row[k] for k in ('mode','operation','size','batch')} |
                       {'mean_cycles':statistics.mean(values),'median_cycles':statistics.median(values),
                        'min_cycles':min(values),'max_cycles':max(values),
                        'sample_cv':statistics.stdev(values)/statistics.mean(values)})
write('variability.csv',variability)
endpoints=[]
for op in ('copy','vadd','gemm'):
    for batch in ('1','16'):
        rows=[r for r in scaling if r['operation']==op and r['batch']==batch]
        endpoints += [rows[0],rows[-1]]
write('selected-results.csv',endpoints)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
labels={'copy':'COPY bytes','vadd':'VADD elements','gemm':'GEMM square dimension'}
colors={'unsecured':'#2864a0','protected':'#bc482c'}
fig,axes=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
for ax,op in zip(axes,labels):
    for mode in ('unsecured','protected'):
        for batch,style in [('1','-'),('16','--')]:
            rows=[r for r in scaling if r['operation']==op and r['batch']==batch]
            ax.errorbar([int(r['size']) for r in rows],[float(r[mode+'_cycles']) for r in rows],
                        yerr=[float(r[mode+'_stdev']) for r in rows],fmt='o'+style,markersize=3,
                        color=colors[mode],label=f'{mode}, batch {batch}',capsize=2)
    ax.set(xscale='log',yscale='log',xlabel=labels[op],ylabel='CPU cycles / batch (mean ± sample SD)')
    if op=='gemm':
        ax.set_xticks([2,4,8,16,32],labels=['2','4','8','16','32'])
        ax.xaxis.set_minor_formatter(NullFormatter())
    ax.grid(alpha=.2)
axes[0].legend(fontsize=8)
fig.suptitle('Synthetic accelerator: complete software-path costs (five measured repetitions)')
for ext in ('png','pdf'):fig.savefig(a.output/('operation-scaling.'+ext),dpi=180)
plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12,3.3),layout='constrained')
for ax,op in zip(axes,labels):
    for batch,style in [('1','o-'),('16','s--')]:
        rows=[r for r in scaling if r['operation']==op and r['batch']==batch]
        ax.plot([int(r['size']) for r in rows],[float(r['protected_over_unsecured']) for r in rows],style,label=f'batch {batch}')
    ax.axhline(1,color='gray',linewidth=1)
    ax.set(xscale='log',yscale='log',xlabel=labels[op],ylabel='Protected / unsecured mean cycles')
    if op=='gemm':
        ax.set_xticks([2,4,8,16,32],labels=['2','4','8','16','32'])
        ax.xaxis.set_minor_formatter(NullFormatter())
    ax.grid(alpha=.2)
axes[0].legend()
fig.suptitle('Ratios include different buffer-management paths; not isolated hardware overhead')
for ext in ('png','pdf'):fig.savefig(a.output/('relative-cost.'+ext),dpi=180)
plt.close(fig)
fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
chosen=[]; names=[]
for op,n in [('copy','65536'),('vadd','16384'),('gemm','32')]:
    for batch in ('1','16'):
        chosen.append(next(r for r in lifecycle if r['mode']=='protected' and r['operation']==op and r['size']==n and r['batch']==batch))
        names.append(f'{op.upper()} {n}\nbatch {batch}')
bottom=[0.]*len(chosen)
for stage in stages:
    values=[float(r[stage])/int(r['batch']) for r in chosen]
    ax.bar(names,values,bottom=bottom,label=stage.removesuffix('_cycles'))
    bottom=[b+v for b,v in zip(bottom,values)]
ax.set_ylabel('Protected CPU cycles / command')
ax.set_title('Largest workloads: lifecycle cost per command; small timer gaps excluded')
ax.legend(ncol=4,fontsize=8)
for ext in ('png','pdf'):fig.savefig(a.output/('lifecycle.'+ext),dpi=180)
plt.close(fig)
summary={'cases':len(scaling)*2,'samples':len(samples),'measured_samples':sum(int(r['repetition'])>0 for r in samples),
         'commands_including_warmups':sum(r['commands'] for r in metrics),
         'max_variability':max(variability,key=lambda r:r['sample_cv']),
         'protected_ratio_min':min(float(r['protected_over_unsecured']) for r in scaling),
         'protected_ratio_max':max(float(r['protected_over_unsecured']) for r in scaling)}
(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('DESC_GPU_PHASE8_ACCOUNTING_AND_FIGURES_PASS')

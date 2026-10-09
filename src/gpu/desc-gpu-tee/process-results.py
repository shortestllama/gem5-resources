#!/usr/bin/env python3
"""Strictly validate complete paired runs before reporting scaling/overhead."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import re

FIELDS='mode operation size batch repetition total_cycles create_cycles config_cycles finalize_cycles launch_cycles execution_cycles stop_cycles destroy_cycles device_ticks dma_read_bytes dma_write_bytes'.split()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('directory',type=Path)
a=p.parse_args()
manifest=json.loads((a.directory/'manifest.json').read_text())
rows=[]; stats=[]; means={}; platforms={}; polls=[]
finalize_diagnostics=[]; execution_diagnostics=[]
matched=manifest.get('protocol') in ('matched-zero-copy-poll-v6',
                                     'matched-optimized-policy-v2')
batched=manifest.get('layout')=='batched-modes'
def read_terminal(run):
    terminals=list(run.glob('*.terminal')) + list(run.glob('*.terminal.device'))
    return '\n'.join(f.read_text(errors='replace') for f in terminals)

def mode_cases(mode):
    run=a.directory/mode
    text=read_terminal(run)
    if f'DESC_GPU_PHASE8_MODE_PASS_{mode}' not in text or '_FAIL' in text:
        raise SystemExit(f'FAIL incomplete mode: {mode}')
    expected=[f'{mode}-{op}-{n}-{batch}' for op,n,batch in manifest['cases']]
    starts=re.findall(r'^PHASE8_CASE_BEGIN,([^\r\n]+)',text,re.M)
    ends=re.findall(r'^PHASE8_CASE_END,([^\r\n]+)',text,re.M)
    matches=list(re.finditer(r'^PHASE8_CASE_BEGIN,([^\r\n]+)\r?\n(.*?)^PHASE8_CASE_END,\1\r?$',text,re.M|re.S))
    if starts!=expected or ends!=expected or [m[1] for m in matches]!=expected:
        raise SystemExit(f'FAIL case order/boundaries: {mode}')
    raw=(run/'stats.txt').read_text()
    blocks=re.findall(r'Begin Simulation Statistics[^\n]*\n(.*?)End Simulation Statistics',raw,re.S)
    # gem5 may emit one extra automatic final dump after the 54 explicit dumps.
    if len(blocks) not in (len(expected),len(expected)+1):
        raise SystemExit(f'FAIL case statistics count: {mode}')
    if raw.count('Begin Simulation Statistics')!=len(blocks):
        raise SystemExit(f'FAIL truncated statistics: {mode}')
    return {label:(m[2],block) for label,m,block in zip(expected,matches,blocks)}

for mode in ('unsecured','protected'):
    grouped=mode_cases(mode) if batched else None
    for op,n,batch in manifest['cases']:
        label=f'{mode}-{op}-{n}-{batch}'
        run=a.directory/(mode if batched else label)
        text=grouped[label][0] if batched else read_terminal(run)
        if 'DESC_GPU_PHASE8_BENCH_PASS' not in text or '_FAIL' in text:
            raise SystemExit(f'FAIL missing PASS or guest failure: {label}')
        samples=[]
        for line in text.splitlines():
            if 'PHASE8_CSV,' not in line: continue
            values=line.split('PHASE8_CSV,',1)[1].strip().split(',')
            if len(values)!=len(FIELDS): raise SystemExit(f'FAIL malformed row: {label}')
            row=dict(zip(FIELDS,values))
            for field in FIELDS[2:]: row[field]=int(row[field])
            if (row['mode'],row['operation'],row['size'],row['batch'])!=(mode,op,n,batch):
                raise SystemExit(f'FAIL mislabeled row: {label}')
            operand_bytes = n if op=='copy' else 4*n if op=='vadd' else 4*n*n
            expected_read = batch*(128+operand_bytes*(1 if op=='copy' else 2))
            expected_write = batch*(64+operand_bytes)
            if row['dma_read_bytes']!=expected_read or row['dma_write_bytes']!=expected_write:
                raise SystemExit(f'FAIL unexpected DMA accounting: {label}')
            if row['total_cycles']<=0 or row['device_ticks']<=0:
                raise SystemExit(f'FAIL nonpositive timing: {label}')
            samples.append(row)
        if sorted(r['repetition'] for r in samples)!=list(range(6)):
            raise SystemExit(f'FAIL expected one warmup and five repetitions: {label}')
        if matched:
            if text.count('DESC_GPU_MATCHED_V6_ZERO_COPY_POLLING')!=1:
                raise SystemExit(f'FAIL missing matched protocol: {label}')
            details=[]
            for line in text.splitlines():
                if not line.startswith('MATCHED_POLLS,'): continue
                parts=line.split(',')[1:]
                if len(parts)!=6 or parts[:2]!=[mode,op] or list(map(int,parts[2:4]))!=[n,batch]:
                    raise SystemExit(f'FAIL mislabeled poll count: {label}')
                rep,count=map(int,parts[4:])
                minimum = batch if manifest.get('protocol')=='matched-zero-copy-poll-v6' else 1
                if count<minimum: raise SystemExit(f'FAIL invalid poll count: {label}')
                details.append({'mode':mode,'operation':op,'size':n,'batch':batch,'repetition':rep,'status_polls':count})
            if sorted(r['repetition'] for r in details)!=list(range(6)):
                raise SystemExit(f'FAIL poll repetition coverage: {label}')
            polls.extend(details)
        if mode=='protected' and manifest.get('protocol')=='matched-optimized-policy-v2':
            final_fields=('operation size batch repetition finalize_cycles total_internal '
                          'entry_fixed dsm_begin descriptor_copy descriptor_validation '
                          'descriptor_hashing descriptor_install policy_digest iopmp_program '
                          'dsm_finalize policy_insert timer_read').split()
            exec_fields=('operation size batch repetition execution_cycles status_cycles '
                         'status_polls completion_cycles device_ticks').split()
            case_final=[]; case_exec=[]
            for line in text.splitlines():
                if line.startswith('FINALIZE_DIAG,'):
                    values=line.split(',')[1:]
                    if len(values)!=len(final_fields):
                        raise SystemExit(f'FAIL malformed FINALIZE diagnostic: {label}')
                    record=dict(zip(final_fields,values))
                    for field in final_fields[1:]: record[field]=int(record[field])
                    if (record['operation'],record['size'],record['batch'])!=(op,n,batch):
                        raise SystemExit(f'FAIL mislabeled FINALIZE diagnostic: {label}')
                    case_final.append(record)
                elif line.startswith('EXEC_DIAG,'):
                    values=line.split(',')[1:]
                    if len(values)!=len(exec_fields):
                        raise SystemExit(f'FAIL malformed execution diagnostic: {label}')
                    record=dict(zip(exec_fields,values))
                    for field in exec_fields[1:]: record[field]=int(record[field])
                    if (record['operation'],record['size'],record['batch'])!=(op,n,batch):
                        raise SystemExit(f'FAIL mislabeled execution diagnostic: {label}')
                    case_exec.append(record)
            if sorted(r['repetition'] for r in case_final)!=list(range(6)) or \
               sorted(r['repetition'] for r in case_exec)!=list(range(6)):
                raise SystemExit(f'FAIL diagnostic repetition coverage: {label}')
            for sample,final,execution in zip(samples,case_final,case_exec):
                if final['finalize_cycles']!=sample['finalize_cycles'] or \
                   execution['execution_cycles']!=sample['execution_cycles'] or \
                   execution['device_ticks']!=sample['device_ticks'] or \
                   final['descriptor_hashing']:
                    raise SystemExit(f'FAIL inconsistent diagnostics: {label}')
            finalize_diagnostics.extend(case_final)
            execution_diagnostics.extend(case_exec)
        rows.extend(samples)
        measured=[r for r in samples if r['repetition']]
        means[mode,op,n,batch]={f:statistics.mean(r[f] for r in measured) for f in FIELDS[5:]}
        means[mode,op,n,batch]['total_stdev']=statistics.stdev(r['total_cycles'] for r in measured)
        # Preserve every scalar statistic in each dump, including CPU/cache/DRAM.
        block=0
        stat_text=('Begin Simulation Statistics\n'+grouped[label][1]) if batched else (run/'stats.txt').read_text()
        for line in stat_text.splitlines():
            if 'Begin Simulation Statistics' in line: block+=1
            parts=line.split()
            if len(parts)<2: continue
            try: value=float(parts[1])
            except ValueError: continue
            stats.append({'run':label,'dump':block,'stat':parts[0],'value':value})
        if mode=='protected' and manifest.get('protocol')=='matched-optimized-policy-v2':
            counters={}
            for line in grouped[label][1].splitlines():
                parts=line.split()
                if len(parts)>=2 and parts[0].startswith('board.trusted_gpu_control.control.descriptor'):
                    counters[parts[0].rsplit('.',1)[-1]]=int(float(parts[1]))
            expected={'descriptorBegins':6*batch,'descriptorWords':6*batch*32,
                      'descriptorCommits':6*batch,'descriptorFailures':0}
            if counters!=expected:
                raise SystemExit(f'FAIL DSM staging FIFO accounting: {label}: {counters}')
        config=json.loads((run/'config.json').read_text())
        board=config['board']
        platform={key:board[key] for key in ('processor','cache_hierarchy','memory')}
        gpu=board['platform']['simplified_gpu']
        platform['timing']={key:gpu[key] for key in
            ('compute_latency','copy_byte_latency','vadd_element_latency','gemm_mac_latency')}
        platforms[mode,op,n,batch]=platform
        if mode=='protected' and platform!=platforms['unsecured',op,n,batch]:
            raise SystemExit(f'FAIL mismatched CPU/cache/memory/timing: {label}')
        # Save actual evaluated configuration, not just requested CLI settings.
        (a.directory/(label+'-platform.json')).write_text(json.dumps(config,indent=2)+'\n')

def write(name,records):
    with (a.directory/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
write('samples.csv',rows); write('gem5-statistics.csv',stats)
if matched: write('matched-polls.csv',polls)
if finalize_diagnostics:
    expected=manifest['gpu_policy']
    misses=sum(bool(r['policy_digest']) for r in finalize_diagnostics)
    if misses!=expected['expected_cache_misses'] or \
       len(finalize_diagnostics)-misses!=expected['expected_cache_hits']:
        raise SystemExit(f'FAIL policy-cache accounting: misses={misses}')
    write('finalize-diagnostics.csv',finalize_diagnostics)
    write('execution-diagnostics.csv',execution_diagnostics)
scaling=[]; lifecycle=[]
for op,n,batch in manifest['cases']:
    u=means['unsecured',op,n,batch]; s=means['protected',op,n,batch]
    scaling.append({'operation':op,'size':n,'batch':batch,
        'unsecured_cycles':u['total_cycles'],'protected_cycles':s['total_cycles'],
        'unsecured_stdev':u['total_stdev'],'protected_stdev':s['total_stdev'],
        'protected_over_unsecured':s['total_cycles']/u['total_cycles'],
        'extra_cycles_per_command':(s['total_cycles']-u['total_cycles'])/batch})
    for mode in ('unsecured','protected'):
        lifecycle.append({'mode':mode,'operation':op,'size':n,'batch':batch,**means[mode,op,n,batch]})
write('operation-scaling.csv',scaling);write('lifecycle-amortization.csv',lifecycle)
print('DESC_GPU_PHASE8_RESULTS_PASS')

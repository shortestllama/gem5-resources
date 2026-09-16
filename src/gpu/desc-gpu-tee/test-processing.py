#!/usr/bin/env python3
"""Synthetic parser fixtures only; never reported as accelerator measurements."""
import json
from pathlib import Path
import subprocess
import tempfile
processor=Path(__file__).with_name('process-results.py')
with tempfile.TemporaryDirectory(prefix='phase8-parser-test-') as tmp:
    d=Path(tmp); (d/'manifest.json').write_text(json.dumps({'cases':[['copy',64,1]]}))
    for mode,total in [('unsecured',100),('protected',150)]:
        run=d/f'{mode}-copy-64-1'; run.mkdir()
        rows=['PHASE8_CSV,'+','.join(map(str,[mode,'copy',64,1,i,total,1,2,3,4,5,6,7,1000,192,128])) for i in range(6)]
        (run/'board.platform.terminal.device').write_text('\n'.join(rows+['DESC_GPU_PHASE8_BENCH_PASS']))
        (run/'stats.txt').write_text('---------- Begin Simulation Statistics ----------\nsimTicks 1000\n')
        (run/'config.json').write_text(json.dumps({'board':{'processor':{},'memory':{},'cache_hierarchy':{},
            'platform':{'simplified_gpu':{k:100 for k in ('compute_latency','copy_byte_latency','vadd_element_latency','gemm_mac_latency')}}}}))
    subprocess.run(['python3',str(processor),tmp],check=True,stdout=subprocess.DEVNULL)
    assert '1.5' in (d/'operation-scaling.csv').read_text()
    old=d/'protected-copy-64-1/board.platform.terminal.device'
    log=d/'protected-copy-64-1/board.platform.terminal'
    old.rename(log)
    subprocess.run(['python3',str(processor),tmp],check=True,stdout=subprocess.DEVNULL)
    original=log.read_text(); log.write_text(original.replace('DESC_GPU_PHASE8_BENCH_PASS',''))
    assert subprocess.run(['python3',str(processor),tmp],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
    log.write_text(original)
    config=d/'protected-copy-64-1/config.json'
    value=json.loads(config.read_text()); value['board']['processor']['cores']=99
    config.write_text(json.dumps(value))
    assert subprocess.run(['python3',str(processor),tmp],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
print('DESC_GPU_PHASE8_PROCESSING_TEST_PASS')

# Multiple cases sharing a boot: preserve exact case/statistics correspondence.
with tempfile.TemporaryDirectory(prefix='phase8-batched-test-') as tmp:
    d=Path(tmp); cases=[['copy',64,1],['copy',128,16]]
    (d/'manifest.json').write_text(json.dumps({'layout':'batched-modes','cases':cases}))
    for mode,total in [('unsecured',100),('protected',150)]:
        run=d/mode;run.mkdir(); lines=[]; blocks=[]
        for index,(op,n,batch) in enumerate(cases):
            label=f'{mode}-{op}-{n}-{batch}'
            lines.append('PHASE8_CASE_BEGIN,'+label)
            lines += ['PHASE8_CSV,'+','.join(map(str,[mode,op,n,batch,i,total,1,2,3,4,5,6,7,1000,batch*(128+n),batch*(64+n)])) for i in range(6)]
            lines += ['DESC_GPU_PHASE8_BENCH_PASS','PHASE8_CASE_END,'+label]
            blocks.append(f'---------- Begin Simulation Statistics ----------\nsimTicks {1000+index}\n---------- End Simulation Statistics ----------\n')
        lines.append('DESC_GPU_PHASE8_MODE_PASS_'+mode)
        (run/'board.platform.terminal').write_text('\r\n'.join(lines)+'\r\n')
        (run/'stats.txt').write_text(''.join(blocks)+blocks[-1])
        (run/'config.json').write_text(json.dumps({'board':{'processor':{},'memory':{},'cache_hierarchy':{},
            'platform':{'simplified_gpu':{k:100 for k in ('compute_latency','copy_byte_latency','vadd_element_latency','gemm_mac_latency')}}}}))
    def invoke():
        return subprocess.run(['python3',str(processor),tmp],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert invoke().returncode==0
    import csv
    with (d/'gem5-statistics.csv').open() as f: stats=list(csv.DictReader(f))
    assert len(stats)==4
    assert [float(row['value']) for row in stats]==[1000,1001,1000,1001]
    log=d/'protected/board.platform.terminal'; original=log.read_text()
    for corrupt in [original.replace('PHASE8_CASE_END,protected-copy-64-1','PHASE8_CASE_END,wrong'),
                    original.replace('DESC_GPU_PHASE8_MODE_PASS_protected',''),
                    original.replace('DESC_GPU_PHASE8_BENCH_PASS','',1),
                    original+'\nDESC_GPU_PHASE8_CAMPAIGN_FAIL\n']:
        log.write_text(corrupt); assert invoke().returncode!=0
    log.write_text(original)
    path=d/'protected/stats.txt'; original=path.read_text()
    path.write_text(original.split('---------- End Simulation Statistics ----------')[0])
    assert invoke().returncode!=0
    path.write_text(original)
    assert invoke().returncode==0
    # The new protocol requires explicit zero-copy/polling identity and details.
    (d/'manifest.json').write_text(json.dumps({'layout':'batched-modes','protocol':'matched-zero-copy-poll-v6','cases':cases}))
    for mode in ('unsecured','protected'):
        log=d/mode/'board.platform.terminal'; text=log.read_text()
        for op,n,batch in cases:
            label=f'{mode}-{op}-{n}-{batch}'
            text=text.replace('PHASE8_CASE_BEGIN,'+label+'\n',
                              'PHASE8_CASE_BEGIN,'+label+'\nDESC_GPU_MATCHED_V6_ZERO_COPY_POLLING\n')
            details='\n'.join(f'MATCHED_POLLS,{mode},{op},{n},{batch},{i},{batch+1}' for i in range(6))
            text=text.replace('PHASE8_CASE_END,'+label,details+'\nPHASE8_CASE_END,'+label)
        log.write_text(text)
    assert invoke().returncode==0
    assert (d/'matched-polls.csv').exists()
    log=d/'protected/board.platform.terminal'; original=log.read_text()
    log.write_text(original.replace('DESC_GPU_MATCHED_V6_ZERO_COPY_POLLING','',1))
    assert invoke().returncode!=0
    log.write_text(original.replace('MATCHED_POLLS,protected,copy,64,1,0,2', 'MATCHED_POLLS,protected,copy,64,1,0,0'))
    assert invoke().returncode!=0
    log.write_text(original); assert invoke().returncode==0
print('DESC_GPU_PHASE8_BATCHED_PROCESSING_TEST_PASS')
print('DESC_GPU_MATCHED_PROCESSING_TEST_PASS')

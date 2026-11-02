"""Reproducible A/10x/100x local context benchmark, never model latency."""
import argparse
import json
import math
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode=True
from sr.integrity import Store, canonical, now, sha
from sr.memory import Memory
from sr.knowledge import Knowledge

ROOT=Path(__file__).resolve().parents[1]

def percentile(values,q):
    return sorted(values)[max(0,math.ceil(q*len(values))-1)]

def dataset(root,scale):
    store=Store(root,create=True);Knowledge(store).initialize();m=Memory(store)
    m.person('SELF',[]);m.person('PERSON_A',['示例'])
    sid=m.source('PERSON_A','chat','明确喜欢散步')['source_id']
    m.claim('PERSON_A','喜欢散步',[sid],'statement','high','preference',store.revision('person:PERSON_A'))
    stamp=now()
    # Bulk fixture creation is outside the timed path. Only irrelevant data grows.
    with store.write('fixture') as db:
        for i in range(20*scale):
            pid='OTHER_'+str(i);db.execute('INSERT INTO people VALUES(?,?)',(pid,'[]'))
            for j in range(5):
                value='无关资料'+str(i)+'_'+str(j)
                db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)',('F'+str(i)+'_'+str(j),pid,'document',value,sha(value),sha(value),1,stamp))
            rule={'id':'UNRELATED_'+str(i),'topic':'review','content':'无关复盘参考'+str(i),'conditions':'仅复盘','limits':'示例','source_refs':['builtin:V01']}
            db.execute('INSERT INTO core_rules VALUES(?,?,?,?)',(1,rule['id'],'review',canonical(rule)))
    store.close()

def execute(root):
    request=canonical({'identifier':'PERSON_A','topic':'daily'})
    start=time.perf_counter_ns()
    proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/social_reply.py'),'--data',str(root),'context'],input=request,capture_output=True,encoding='utf-8',check=True)
    elapsed=(time.perf_counter_ns()-start)/1e6
    result=json.loads(proc.stdout)['result']
    assert result['path']=='FAST' and result['person_id']=='PERSON_A'
    assert result['profile']['claims'][0]['content']=='喜欢散步'
    assert len(result['theory'])<=16
    assert '无关资料' not in canonical(result)
    return elapsed,result

def run(samples):
    rows=[]
    with tempfile.TemporaryDirectory(prefix='social-reply-bench-') as tmp:
        for scale in [1,10,100]:
            root=Path(tmp)/str(scale);dataset(root,scale)
            cold=[];warm=[];cold_reads=[];warm_reads=[];context_bytes=[];cold_prepare=[];warm_prepare=[];cold_open=[];warm_open=[]
            for _ in range(samples):
                with sqlite3.connect(root/'social-reply.sqlite3') as db:db.execute('DELETE FROM cache')
                elapsed,result=execute(root);cold.append(elapsed);cold_reads.append(result['diagnostics']['sql_reads'])
                cold_prepare.append(result['diagnostics']['context_prepare_ms'])
                cold_open.append(result['diagnostics']['data_open_ms'])
                elapsed,result=execute(root);warm.append(elapsed);warm_reads.append(result['diagnostics']['sql_reads'])
                warm_prepare.append(result['diagnostics']['context_prepare_ms'])
                warm_open.append(result['diagnostics']['data_open_ms'])
                assert result['cache_hit']
                context_bytes.append(len(canonical({k:v for k,v in result.items() if k not in {'cache_hit','diagnostics'}}).encode('utf-8')))
            rows.append({'scale':scale,'unrelated_people':20*scale,'unrelated_sources':100*scale,'unrelated_rules':20*scale,
                         'samples_each':samples,'cold_p50_ms':statistics.median(cold),'cold_p95_ms':percentile(cold,.95),
                         'warm_p50_ms':statistics.median(warm),'warm_p95_ms':percentile(warm,.95),
                         'cold_prepare_p50_ms':statistics.median(cold_prepare),'cold_prepare_p95_ms':percentile(cold_prepare,.95),
                         'warm_prepare_p50_ms':statistics.median(warm_prepare),'warm_prepare_p95_ms':percentile(warm_prepare,.95),
                         'raw_samples':{'cold_process_ms':cold,'warm_process_ms':warm,'cold_prepare_ms':cold_prepare,'warm_prepare_ms':warm_prepare,'cold_open_ms':cold_open,'warm_open_ms':warm_open},
                         'cold_sql_reads':max(cold_reads),'warm_sql_reads':max(warm_reads),
                         'helper_invocations_per_request':1,'logical_private_data_files':1,
                         'context_utf8_bytes':max(context_bytes),'context_tokens':None,
                         'host_tool_read_count':None,'first_model_reply_ms':None,'complete_model_request_ms':None,
                         'routing_and_profile_checks':'measured passed'})
    baseline=rows[0]
    alerts=[]
    for row in rows[1:]:
        if row['warm_p95_ms']>1.2*baseline['warm_p95_ms']:
            alerts.append({'scale':row['scale'],'reason':'warm helper p95 exceeded 20%; investigate environment and query counts, not a model-speed claim'})
    return {'version':2,'environment':{'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'system':platform.system()},
            'measurement':'fresh Python helper process including startup and indexed context preparation; no language-model call',
            'percentile_method':'nearest rank','rows':rows,'alerts':alerts,
            'unverified':['actual host tool-read telemetry','host tokenizer and billable tokens','first effective model reply latency','complete model generation latency','broad model quality regression'],
            'token_reason':'host tokenizer and usage unavailable; UTF-8 bytes are measured, not converted to invented token counts'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--samples',type=int,default=30);args=p.parse_args()
    if not 5<=args.samples<=200:p.error('samples must be between 5 and 200')
    print(canonical(run(args.samples)))

if __name__=='__main__':main()

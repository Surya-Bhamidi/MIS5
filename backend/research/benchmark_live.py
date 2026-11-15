"""Exercise a running HTTP service with archived telemetry and induced outages.

This measures local shadow-mode handling, not a production sensor deployment
or the effectiveness of a real defensive intervention.
"""
from itertools import combinations
from pathlib import Path
import argparse
import hashlib
import json
import pickle
import time

import numpy as np
import requests
from threadpoolctl import threadpool_limits
import extended_study as study
import selective_fusion as selective
from streaming_forecast import ExpertStream,ForecastStream

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'
SENSORS=['aminer','suricata','wazuh']


def distribution(values):
    return dict(samples=len(values),median_ms=float(np.median(values)),p95_ms=float(np.percentile(values,95)),max_ms=float(max(values)))


def run(base='http://127.0.0.1:8001'):
    session=requests.Session()
    def request(method,path,**kwargs):
        response=session.request(method,base+'/api/live/'+path,timeout=60,**kwargs)
        response.raise_for_status()
        return response.json()
    model_path=ROOT/'data/research/live/model.pkl'
    content=model_path.read_bytes()
    manifest=json.loads(model_path.with_suffix('.json').read_text())
    assert hashlib.sha256(content).hexdigest()==manifest['sha256']
    package=pickle.loads(content)
    name=package['test']
    ep=study.load('ait')[name]
    root=next(r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text()) if r['scenario']==name)
    mask=(ep['times']<root)&(ep['times']>=root-180*60)
    probe={**ep,'counts':ep['counts'][mask],'times':ep['times'][mask]}
    checks=[];expected_full=None
    for key,item in package['experts'].items():
        stream=ExpertStream(item['bundle'],item['calibrators'])
        actual=np.array([stream.step({str(n):float(v) for n,v in zip(probe['names'],row)}) for row in probe['counts']])
        expected=selective.predict_current(item['bundle'],probe,key.split('+'),{'pooled_fixed_blend':item['calibrators']})['risk']
        error=float(np.max(np.abs(actual-expected)))
        assert error<1e-9,(key,error)
        checks.append(dict(available=key,stream_batch_max_error=error,bins=len(actual)))
        if key=='+'.join(SENSORS):expected_full=expected
        print(f'Stream verified: {key}, {len(actual)} informative bins, error {error:.3g}',flush=True)
    # Paired same-process comparison against the previous eager design.
    # Both paths see the same buckets and start from the same model state.
    eager={key:ExpertStream(item['bundle'],item['calibrators']) for key,item in package['experts'].items()}
    lazy=ForecastStream(package)
    eager_ms=[];lazy_ms=[]
    for timestamp,row in zip(probe['times'],probe['counts']):
        counts={str(n):float(v) for n,v in zip(probe['names'],row) if v}
        start=time.perf_counter()
        previous={key:expert.step(counts) for key,expert in eager.items()}
        eager_ms.append((time.perf_counter()-start)*1000)
        start=time.perf_counter();current=lazy.step(float(timestamp),counts,set(SENSORS))
        lazy_ms.append((time.perf_counter()-start)*1000)
        np.testing.assert_array_equal(current['risk'],previous['aminer+suricata+wazuh'])
    stream_id=request('POST','streams',json={'mode':'replay','warning_profile':'responsive'})['stream_id']
    latencies=[];processing=[];acks=[];completions=[];notifications=0
    try:
        for i,(timestamp,row) in enumerate(zip(probe['times'],probe['counts'])):
            counts={str(n):float(v) for n,v in zip(probe['names'],row) if v}
            start=time.perf_counter()
            result=request('POST',f'streams/{stream_id}/observations',json=dict(timestamp=float(timestamp),counts=counts,heartbeats={s:float(timestamp) for s in SENSORS}))
            latencies.append((time.perf_counter()-start)*1000)
            processing.append(result['processing_latency_ms'])
            np.testing.assert_allclose(result['risk'],expected_full[i],atol=1e-9,rtol=0)
            losses=study.decision_costs(expected_full[i:i+1],True,20,.8,1)[0]
            np.testing.assert_allclose(result['modeled_losses'],losses,atol=1e-9,rtol=0)
            assert result['recommended_action']==study.ACTIONS[int(losses.argmin())][0]
            if result['notify']:
                notifications+=1
                path=f"notifications/{result['notification_id']}/response"
                ack=request('POST',path,json=dict(status='acknowledged',note='Benchmark consumer receipt; no defense executed'))
                completed=request('POST',path,json=dict(status='completed',note='Benchmark no-op handler completed; no defense executed'))
                acks.append(ack['acknowledgment_latency_ms']);completions.append(completed['completion_latency_ms'])
            if i%60==59:print(f'HTTP replay: {i+1}/{len(probe["times"])} observations',flush=True)
    finally:request('DELETE',f'streams/{stream_id}')
    # Each subset is exercised in an actual running stream; stale counts from
    # failed sensors are deliberately retained to ensure they are ignored.
    stream_id=request('POST','streams',json={'mode':'replay'})['stream_id']
    outages=[]
    try:
        tick=0
        histories={key:[] for key in package['experts']}
        for size in (3,2,1,0,3):
            for subset in combinations(SENSORS,size):
                for _ in range(3):
                    timestamp=float(probe['times'][-1]+(tick+1)*60);tick+=1
                    result=request('POST',f'streams/{stream_id}/observations',json=dict(timestamp=timestamp,counts={s+':OTHER':3 for s in SENSORS},heartbeats={s:timestamp for s in subset}))
                    assert result['available']==('+'.join(sorted(subset)) or 'none')
                    assert (result['status']=='ok')==bool(subset)
                    if not subset:assert result['risk'] is None and result['recommended_action'] is None and not result['notify']
                    for expert_key in histories:
                        histories[expert_key] = histories[expert_key]+[timestamp] if set(expert_key.split('+'))<=set(subset) else []
                    if subset:
                        item=package['experts'][result['available']]
                        history=histories[result['available']]
                        reference=dict(times=np.array(history),counts=np.full((len(history),3),3.),names=np.array([s+':OTHER' for s in SENSORS]))
                        expected=selective.predict_current(item['bundle'],reference,subset,{'pooled_fixed_blend':item['calibrators']})
                        np.testing.assert_allclose(result['risk'],expected['risk'][-1],atol=1e-9,rtol=0)
                        assert result['history_minutes']==min(60,len(history))
                outages.append(dict(available=result['available'],status=result['status'],history_minutes=result.get('history_minutes'),passed=True))
    finally:request('DELETE',f'streams/{stream_id}')
    # Also exercise the wall-clock validation path with actual current time.
    stream_id=request('POST','streams',json={'mode':'live'})['stream_id']
    try:
        now=time.time()
        result=request('POST',f'streams/{stream_id}/observations',json=dict(timestamp=now,counts={},heartbeats={s:now for s in SENSORS}))
        assert result['mode']=='live' and result['status']=='ok'
    finally:request('DELETE',f'streams/{stream_id}')
    output=dict(scope='Local HTTP service with accelerated archived fox telemetry, induced outages, and a current-time smoke observation; no live sensor deployment or defense',
                model_fold=name,model_sha256=manifest['sha256'],observations=len(latencies),
                http_round_trip=distribution(latencies),server_processing=distribution(processing),
                notifications=notifications,receipts_acknowledged=len(acks),noop_handlers_completed=len(completions),
                acknowledgment=distribution(acks) if acks else None,noop_completion=distribution(completions) if completions else None,
                stream_equivalence=checks,outage_checks=outages,current_time_live_smoke_passed=True,
                http_predictions_and_actions_verified=True,dynamic_outage_predictions_verified=True,
                warning_profile='responsive',
                paired_inference_optimization=dict(previous_eager=distribution(eager_ms),current_selected_only=distribution(lazy_ms),
                    median_reduction_percent=100*(1-np.median(lazy_ms)/np.median(eager_ms)),
                    predictions_identical=True,scope='Same-process paired inference comparison; no sensor collection or network latency'),
                response_effectiveness='Not measured: acknowledgments and no-op completions are not attack prevention')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'live_benchmark.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8001')
    with threadpool_limits(limits=1):run(parser.parse_args().base_url)

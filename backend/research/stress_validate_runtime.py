"""Exhaustive retained-fold conformance and controlled local API operations.

Uses only local archives/refitted packages. Every API write goes to a temporary
SQLite database. No network attack or defensive actuator is involved.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import argparse
import hashlib
import json
import logging
import pickle
import sqlite3
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import extended_study as study
import selective_fusion as selective
from streaming_forecast import ExpertStream
from audit_operational_improvements import reference_policy,reference_metrics
from app.models.package_validation import validate_package
from app.models.warning_profiles import profile_config

OUT=ROOT/'experiments/operational_improvements'
MODELS=ROOT/'data/research/stress_models'
SENSORS=('aminer','suricata','wazuh')


def losses(risk):
    result=[]
    for delay,effect,disruption in ((0,0.,0.),(2,.45,.1),(5,.8,.5),(1,.95,2.)):
        early=np.zeros(len(risk)) if not delay else risk[:,[1,2,5,10,15,30].index(delay)]
        result.append(disruption+20*risk[:,-1]-16*effect*np.maximum(0,risk[:,-1]-early))
    return np.stack(result,axis=1)


def operation_flows(package,episode,onset):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import live_router as live
    logging.getLogger('httpx').setLevel(logging.WARNING)
    indices=np.flatnonzero(episode['times']<onset)[-72:]
    subsets=['aminer+suricata+wazuh','aminer+suricata','aminer+wazuh','suricata+wazuh','aminer','suricata','wazuh','none','aminer+suricata+wazuh']
    reports=[]
    with TemporaryDirectory() as folder,patch.object(live,'MODEL',MODELS/f"{package['test']}.pkl"),patch.object(live,'DB',Path(folder)/'operations.sqlite3'):
        live.streams.clear()
        with TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',50000),raise_server_exceptions=False) as client:
            for profile in ('responsive','confirmed'):
                created=client.post('/api/live/streams',json={'mode':'replay','warning_profile':profile})
                if created.status_code!=200:raise AssertionError(created.text)
                identifier=created.json()['stream_id'];histories={key:[] for key in package['experts']}
                previous_time=None;previous_context=None;segment_times=[];segment_scores=[];carry=-np.inf;last_notification=-np.inf
                notices=[];retry_checks=0;conflict_checks=0;faults=0;maximum=0.;actions={}
                names=package['experts'][subsets[0]]['bundle']['vocabulary'];mapping={n:i for i,n in enumerate(names)}
                for tick,index in enumerate(indices):
                    timestamp=float(episode['times'][index])+(60 if tick>=55 else 0)
                    key=subsets[tick//8];healthy=set(key.split('+')) if key!='none' else set()
                    counts={str(n):float(v) if str(n).split(':')[0] in healthy else 1e12 for n,v in zip(episode['names'],episode['counts'][index]) if v or str(n).split(':')[0] not in healthy}
                    if tick==23:
                        for sensor in healthy:counts[sensor+':UNSEEN_TEST_DETECTOR']=7.
                    if tick==35:counts[next(iter(sorted(healthy)))+':UNSEEN_TEST_DETECTOR']=1e300
                    heartbeats={s:timestamp if s in healthy else timestamp-91 for s in SENSORS}
                    if tick%2:heartbeats={s:t for s,t in heartbeats.items() if s in healthy}
                    body=dict(timestamp=timestamp,counts=counts,heartbeats=heartbeats)
                    aligned=np.zeros(len(names))
                    for token,value in counts.items():
                        if token.split(':')[0] in healthy:
                            feature=token if token in mapping else token.split(':')[0]+':OTHER'
                            aligned[mapping[feature]]+=value
                    gap=previous_time is not None and timestamp-previous_time!=60
                    for expert_key in histories:
                        if not set(expert_key.split('+'))<=healthy:histories[expert_key]=[]
                        else:
                            if gap:histories[expert_key]=[]
                            histories[expert_key].append((timestamp,aligned.copy()))
                    if key!=previous_context or gap:
                        segment_times=[];segment_scores=[];carry=last_notification
                    expected=None;expected_warning=False;expected_notice=False;expected_start=False
                    if healthy:
                        item=package['experts'][key];history=histories[key]
                        reference=dict(times=np.array([r[0] for r in history]),counts=np.array([r[1] for r in history]),names=names)
                        expected=selective.predict_current(item['bundle'],reference,sorted(healthy),{'pooled_fixed_blend':item['calibrators']})['risk'][-1]
                        segment_times.append(timestamp);segment_scores.append(expected[-1])
                        flags,notifies=reference_policy(np.array(segment_times),np.array(segment_scores),item['threshold'],asdict(profile_config(profile)),carry)
                        expected_warning=bool(flags[-1]);expected_notice=bool(notifies[-1]);expected_start=expected_warning and (len(flags)==1 or not flags[-2])
                    if expected_notice:last_notification=timestamp
                    if expected_notice and faults==0:
                        with patch.object(live,'database',side_effect=sqlite3.OperationalError('controlled persistence fault')):
                            failed=client.post(f'/api/live/streams/{identifier}/observations',json=body)
                        assert failed.status_code==503,failed.text
                        assert live.streams[identifier]['forecast'].last_time==previous_time
                        faults+=1
                    response=client.post(f'/api/live/streams/{identifier}/observations',json=body)
                    assert response.status_code==200,response.text
                    result=response.json();assert result['available']==key
                    assert result['warning']==expected_warning and result['notify']==expected_notice and result['episode_start']==expected_start
                    if healthy:
                        error=float(np.max(np.abs(np.array(result['risk'])-expected)));maximum=max(maximum,error)
                        assert error<1e-9,(package['test'],key,profile,error)
                        assert result['history_minutes']==min(60,len(histories[key]))
                        np.testing.assert_allclose(result['modeled_losses'],losses(expected[None,:])[0],rtol=0,atol=1e-12)
                        assert result['recommended_action']==('Monitor','Restrict','Block','Isolate')[int(np.argmin(losses(expected[None,:])[0]))]
                        actions[result['recommended_action']]=actions.get(result['recommended_action'],0)+1
                    else:assert result['risk'] is None and result['recommended_action'] is None and not result['notify']
                    if tick in (10,30,50):
                        retry=client.post(f'/api/live/streams/{identifier}/observations',json={**body,'counts':dict(reversed(list(counts.items())))})
                        assert retry.status_code==200 and retry.json()['idempotent_replay']
                        assert retry.json()['notification_id']==result['notification_id'];retry_checks+=1
                    if tick==30:
                        changed={**body,'counts':{**counts,'aminer:conflict-fixture':1}}
                        assert client.post(f'/api/live/streams/{identifier}/observations',json=changed).status_code==409
                        conflict_checks+=1
                    if result['notify']:
                        notice=result['notification_id'];notices.append(notice)
                        url=f'/api/live/notifications/{notice}/response'
                        ack=client.post(url,json={'status':'acknowledged','note':'Controlled local receipt; no defense'})
                        assert ack.status_code==200 and ack.json()['acknowledgment_latency_ms']>=0
                        repeated=client.post(url,json={'status':'acknowledged'})
                        assert repeated.json()['acknowledgment_latency_ms']==ack.json()['acknowledgment_latency_ms']
                        terminal='completed' if len(notices)%2 else 'failed'
                        receipt=client.post(url,json={'status':terminal,'note':'First terminal receipt; no defense'})
                        assert receipt.status_code==200 and receipt.json()['resolution_latency_ms'] is not None
                        assert (receipt.json()['completion_latency_ms'] is not None)==(terminal=='completed')
                        assert client.post(url,json={'status':'failed' if terminal=='completed' else 'completed'}).status_code==409
                    previous_time=timestamp;previous_context=key
                with live.database() as db:
                    stored=db.execute('SELECT payload FROM warnings WHERE stream=?',(identifier,)).fetchall()
                    assert len(stored)==len(notices)
                    for row in stored:
                        payload=json.loads(row[0]);assert payload['warning_profile']==profile and payload['stream_mode']=='replay'
                        assert payload['bucket_to_notification_ms'] is None
                assert client.delete(f'/api/live/streams/{identifier}').status_code==200
                assert client.delete(f'/api/live/streams/{identifier}').status_code==404
                reports.append(dict(profile=profile,observations=len(indices),notifications=len(notices),retry_checks=retry_checks,
                                    conflict_checks=conflict_checks,persistence_faults_recovered=faults,max_risk_error=maximum,
                                    response_operations_verified=True,actions=actions,passed=True))
    return reports


def verify_fold(test):
    with threadpool_limits(limits=1):
        path=MODELS/f'{test}.pkl';content=path.read_bytes();manifest=json.loads(path.with_suffix('.json').read_text())
        assert hashlib.sha256(content).hexdigest()==manifest['sha256']
        package=validate_package(pickle.loads(content));episode=study.load('ait')[test]
        roots={r['scenario']:r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text())}
        rows=json.loads((OUT/'evaluation.json').read_text())['campaigns'];checks=[]
        raw={k:episode[k] for k in ('counts','times','names')}
        changed={**raw,'truth':np.full(len(raw['times']),999),'onset':-1.}
        prefix=max(1,int(np.sum(raw['times']<roots[test]))-5)
        attack=np.flatnonzero(raw['times']<roots[test])[-180:]
        for key,item in package['experts'].items():
            cal={'pooled_fixed_blend':item['calibrators']};available=key.split('+')
            actual=selective.predict_current(item['bundle'],raw,available,cal)['risk']
            with np.load(ROOT/'experiments/current_version/predictions'/f'ait_{test}_{key}_pooled_fixed_blend.npz') as frozen:
                error=float(np.max(np.abs(actual-frozen['risk'])))
            assert error<1e-9,(test,key,error)
            assert np.isfinite(actual).all() and (actual>=0).all() and (actual<=1).all() and (np.diff(actual,axis=1)>=0).all()
            poisoned=selective.predict_current(item['bundle'],changed,available,cal)['risk']
            np.testing.assert_array_equal(actual,poisoned)
            partial={**raw,'times':raw['times'][:prefix],'counts':raw['counts'][:prefix]}
            np.testing.assert_allclose(selective.predict_current(item['bundle'],partial,available,cal)['risk'],actual[:prefix],atol=1e-9,rtol=0)
            np.testing.assert_allclose(study.decision_costs(actual,True,20,.8,1),losses(actual),atol=1e-12,rtol=0)
            probe={**raw,'times':raw['times'][attack],'counts':raw['counts'][attack]}
            expected=selective.predict_current(item['bundle'],probe,available,cal)['risk'];stream=ExpertStream(item['bundle'],item['calibrators'])
            observed=np.array([stream.step({str(n):float(v) for n,v in zip(probe['names'],row) if v}) for row in probe['counts']])
            stream_error=float(np.max(np.abs(observed-expected)));assert stream_error<1e-9
            mask=raw['times']<roots[test];times=raw['times'][mask]
            for horizon in (15,30):
                saved=next(r for r in rows if (r['campaign'],r['available'],r['horizon'])==(test,key,horizon))
                scores=actual[mask,[1,2,5,10,15,30].index(horizon)];positive=times+horizon*60>=roots[test]
                assert abs(float(np.mean((scores-positive)**2))-saved['brier'])<1e-12
                for profile,mode in [('responsive','baseline'),('confirmed','improved')]:
                    flags,notices=reference_policy(times,scores,saved['threshold'],asdict(profile_config(profile)))
                    assert reference_metrics(times,roots[test],horizon,flags,notices)==saved[mode]
            checks.append(dict(available=key,forecast_values=int(actual.size),archive_max_error=error,
                               stream_max_error=stream_error,prefix_causal=True,target_labels_ignored=True,
                               coherent_probabilities=True,modeled_action_losses_verified=True,metrics_verified=True))
        operations=operation_flows(package,episode,roots[test])
        return dict(campaign=test,experts=checks,operations=operations,passed=True)


def run(workers):
    sources=[Path(__file__),ROOT/'backend/app/routers/live_router.py',ROOT/'backend/app/request_safety.py',
             ROOT/'backend/app/models/package_validation.py',ROOT/'backend/research/streaming_forecast.py',
             ROOT/'backend/app/models/warning_policy.py',ROOT/'backend/app/models/warning_profiles.py',
             ROOT/'backend/app/models/onset_decision.py',ROOT/'backend/app/models/decision_network.py',
             ROOT/'backend/app/models/pipeline.py',ROOT/'backend/app/routers/pipeline_router.py',
             ROOT/'backend/app/routers/legacy_schemas.py',ROOT/'backend/app/main.py',
             ROOT/'backend/app/artifact_store.py',ROOT/'backend/app/ingestion/database.py',
             ROOT/'backend/research/audit_operational_improvements.py']
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(verify_fold,test):test for test in study.load('ait')}
        for future in as_completed(futures):
            result=future.result();results.append(result)
            print(f"Verified {result['campaign']}: 7 sensor experts, 2 controlled API operation flows",flush=True)
    for relative,digest in hashes.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise RuntimeError('Runtime source changed during verification; rerun the check')
    output=dict(passed=True,scope='All eight original research folds; local archived attacks, induced input faults and temporary-database API operations',
                campaigns=len(results),experts=sum(len(r['experts']) for r in results),
                forecast_values_checked=sum(e['forecast_values'] for r in results for e in r['experts']),
                operation_observations=sum(o['observations'] for r in results for o in r['operations']),
                exact_retries_checked=sum(o['retry_checks'] for r in results for o in r['operations']),
                conflicts_rejected=sum(o['conflict_checks'] for r in results for o in r['operations']),
                persistence_faults_recovered=sum(o['persistence_faults_recovered'] for r in results for o in r['operations']),
                notifications_exercised=sum(o['notifications'] for r in results for o in r['operations']),
                maximum_archive_error=max(e['archive_max_error'] for r in results for e in r['experts']),
                maximum_stream_error=max(e['stream_max_error'] for r in results for e in r['experts']),
                results=sorted(results,key=lambda r:r['campaign']),source_sha256=hashes,
                limitation='Functional conformance and retained-campaign evaluation; not proof of global optimality, live attack prevention or independent generalization')
    (OUT/'stress_validation.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k not in ('results','source_sha256')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if not 1<=args.workers<=4:parser.error('Use one to four workers')
    run(args.workers)

"""Independently reconstruct claims and verify actual sensor-switching inference."""
from pathlib import Path
import hashlib
import json
import pickle
import sys
from dataclasses import asdict

import numpy as np
from threadpoolctl import threadpool_limits
import extended_study as study
import selective_fusion as selective
from streaming_forecast import ForecastStream

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.models.warning_policy import WarningPolicy
from app.models.warning_profiles import profile_config
OUT=ROOT/'experiments/operational_improvements'


def run_lengths(mask):
    indices=np.arange(len(mask))
    return np.where(mask,indices-np.maximum.accumulate(np.where(mask,-1,indices)),0)


def reference_policy(times,scores,threshold,config=None,initial_notification=-np.inf):
    """Batch oracle: run lengths, then episode/notification transitions.

    Deliberately does not call WarningPolicy or its configuration class.
    Archived inputs have exactly one-minute spacing and fixed sensor context.
    """
    np.testing.assert_array_equal(np.diff(times),np.full(len(times)-1,60.))
    config=config or dict(confirmations=2,clear_confirmations=2,clear_ratio=.8,
                          max_hold_below_seconds=120,cooldown_seconds=300,fast_ratio=None)
    high=scores>=threshold
    confirm=run_lengths(high)>=config['confirmations']
    if config.get('fast_ratio') is not None:confirm |= high & (scores>=threshold*config['fast_ratio'])
    clear=(run_lengths(scores<threshold*config['clear_ratio'])>=config['clear_confirmations'])|(
        run_lengths(~high)>=config['max_hold_below_seconds']/60+1)
    warning=np.zeros(len(times),dtype=bool);notifications=warning.copy()
    active=sent=False;last_sent=initial_notification
    for i,timestamp in enumerate(times):
        if clear[i]:active=False
        if confirm[i] and not active:active=True;sent=False
        if active and not sent and high[i] and timestamp-last_sent>=config['cooldown_seconds']:
            notifications[i]=sent=True;last_sent=timestamp
        warning[i]=active
    return warning,notifications


def reference_metrics(times,onset,horizon,warning,notifications):
    remaining=onset-times
    positive=(remaining>0)&(remaining<=horizon*60)
    starts=warning&~np.r_[False,warning[:-1]]
    result={}
    for mask,key,lead_key in ((notifications,'timely_notification','notification_lead_minutes'),
                              (starts,'timely_warning_episode','episode_lead_minutes')):
        valid=np.flatnonzero(mask&positive)
        result[key]=int(bool(len(valid)))
        result[lead_key]=float(remaining[valid[0]]/60) if len(valid) else None
    result.update(false_notifications=int(np.sum(notifications&~positive)),
                  false_warning_episodes=int(np.sum(starts&~positive)),
                  negative_warning_minutes=int(np.sum(warning&~positive)),notifications=int(notifications.sum()))
    return result


def run():
    saved=json.loads((OUT/'evaluation.json').read_text())
    roots={r['scenario']:r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text())}
    originals=json.loads((ROOT/'experiments/selective_fusion/scored.json').read_text())
    thresholds=json.loads((ROOT/'experiments/current_version/thresholds.json').read_text())
    checked=0
    for row in saved['campaigns']:
        name,available,horizon=row['campaign'],row['available'],row['horizon']
        path=ROOT/'experiments/current_version/predictions'/f'ait_{name}_{available}_pooled_fixed_blend.npz'
        with np.load(path,allow_pickle=False) as data:
            mask=data['times']<roots[name]
            times=data['times'][mask];scores=data['risk'][mask,data['horizons'].tolist().index(horizon)]
        threshold=next(r['threshold'] for r in thresholds if r['test']==name and r['available']==available and r['horizon']==horizon and r['budget']==1)
        assert row['threshold']==threshold
        raw=scores>=threshold
        starts=raw&~np.r_[False,raw[:-1]]
        responsive=WarningPolicy(profile_config('responsive'))
        response_trace=[responsive.update(float(t),float(p),threshold,available) for t,p in zip(times,scores)]
        np.testing.assert_array_equal([r['warning'] for r in response_trace],raw)
        np.testing.assert_array_equal([r['notify'] for r in response_trace],starts)
        assert row['baseline']==reference_metrics(times,roots[name],horizon,raw,starts)
        warning,notifications=reference_policy(times,scores,threshold)
        assert row['improved']==reference_metrics(times,roots[name],horizon,warning,notifications),(name,available,horizon)
        original=next(r for r in originals if r['scenario']==name and r['available']==available and r['horizon']==horizon and r['mode']=='pooled_fixed_blend' and r['endpoint']=='successful_root' and r['budget']==1 and r['delay_minutes']==0)
        assert row['baseline']['timely_notification']==original['strict_warning_recall']
        assert row['baseline']['false_warning_episodes']==original['false_warning_episodes']
        assert row['baseline']['negative_warning_minutes']==original['negative_warning_minutes']
        assert abs(row['brier']-original['brier'])<1e-12
        checked+=1
    # Check every aggregate, not only the main positive result.
    for summary in saved['summary']:
        group=[r for r in saved['campaigns'] if r['available']==summary['available'] and r['horizon']==summary['horizon']]
        assert summary['campaigns']==len(group)==8
        for mode in ('baseline','improved'):
            for key,value in summary[mode].items():
                if key=='mean_notification_lead_minutes':
                    leads=[r[mode]['notification_lead_minutes'] for r in group if r[mode]['notification_lead_minutes'] is not None]
                    expected=float(np.mean(leads)) if leads else None
                else:expected=sum(r[mode][key] for r in group)
                assert value==expected,(summary['available'],summary['horizon'],mode,key)
        assert summary['mean_brier_unchanged']==float(np.mean([r['brier'] for r in group]))
    model_path=ROOT/'data/research/live/model.pkl'
    content=model_path.read_bytes();manifest=json.loads(model_path.with_suffix('.json').read_text())
    assert hashlib.sha256(content).hexdigest()==manifest['sha256']
    package=pickle.loads(content)
    assert package['test'] not in package['train'] and package['validation'] not in package['train']
    ep=study.load('ait')[package['test']]
    frozen_meta=json.loads((ROOT/'experiments/current_version/metadata.json').read_text())
    archive_checks=[]
    for key,item in package['experts'].items():
        metadata=next(r for r in frozen_meta if r['test']==package['test'] and r['available']==key)
        assert item['calibrators']==metadata['calibrators']['pooled_fixed_blend']
        expected=selective.predict_current(item['bundle'],ep,key.split('+'),{'pooled_fixed_blend':item['calibrators']})['risk']
        with np.load(ROOT/'experiments/current_version/predictions'/f"ait_{package['test']}_{key}_pooled_fixed_blend.npz") as data:
            error=float(np.max(np.abs(expected-data['risk'])))
        assert error<1e-9
        archive_checks.append(dict(available=key,archive_max_error=error))
    # Different observation values, partial outages, full outage, a skipped
    # bucket, recovery, and poisoned data from unavailable sensors.
    clean=ForecastStream(package);poisoned=ForecastStream(package)
    histories={key:[] for key in package['experts']}
    sequences=[('aminer+suricata+wazuh',5),('aminer+wazuh',4),('wazuh',4),('none',2),
               ('aminer+suricata',4),('suricata',4),('suricata+wazuh',4),('aminer',4),('aminer+suricata+wazuh',5)]
    probe_indices=np.flatnonzero(ep['times']<roots[package['test']])[-40:]
    tick=0;previous=None;maximum=0.;outage_checks=[]
    for available,length in sequences:
        for local_index in range(length):
            i=probe_indices[tick];timestamp=float(ep['times'][i])
            if tick>=25:timestamp+=60 # one skipped minute
            healthy=set(available.split('+')) if available!='none' else set()
            values=ep['counts'][i].copy()
            clean_counts={str(n):float(v) for n,v in zip(ep['names'],values) if str(n).split(':')[0] in healthy}
            poison_counts={str(n):float(v) if str(n).split(':')[0] in healthy else 1e12 for n,v in zip(ep['names'],values)}
            actual=clean.step(timestamp,clean_counts,healthy)
            other=poisoned.step(timestamp,poison_counts,healthy)
            assert actual['risk']==other['risk']
            for expert_key in histories:
                if not set(expert_key.split('+'))<=healthy:histories[expert_key]=[]
                else:
                    if previous is not None and timestamp-previous!=60:histories[expert_key]=[]
                    histories[expert_key].append((timestamp,values))
            if healthy:
                history=histories[available];item=package['experts'][available]
                reference=dict(times=np.array([r[0] for r in history]),counts=np.array([r[1] for r in history]),names=ep['names'])
                expected=selective.predict_current(item['bundle'],reference,list(healthy),{'pooled_fixed_blend':item['calibrators']})
                error=float(np.max(np.abs(np.array(actual['risk'])-expected['risk'][-1])))
                maximum=max(maximum,error);assert error<1e-9
                assert actual['recommended_action']==expected['recommended_action']
                assert actual['history_minutes']==min(60,len(history))
            else:assert actual['risk'] is None and actual['recommended_action'] is None
            previous=timestamp;tick+=1
        outage_checks.append(dict(available=available,bins=length,passed=True))
    hashes=json.loads((OUT/'inputs.json').read_text())
    for relative,expected in hashes.items():assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected
    report=dict(passed=True,paired_campaign_horizon_sensor_checks=checked,aggregate_checks=len(saved['summary']),
                default_warning_profile='responsive',responsive_matches_original_cases=checked,
                baseline_matches_original_score_tables=True,independent_warning_oracle_matches=True,
                unchanged_frozen_calibrators=True,model_fitting_excludes_test_and_validation=True,
                refitted_archive_checks=archive_checks,dynamic_outage_checks=outage_checks,
                dynamic_stream_batch_max_error=maximum,unavailable_sensor_poisoning_has_no_effect=True,
                skipped_bucket_and_recovery_verified=True,input_hashes_verified=len(hashes),
                interpretation=dict(alarm_claim='Exploratory 30-minute result; no probability-accuracy gain',
                  sensor_claim='Automatic routing is new; existing experts beat a naive zero-fill comparator on one inspected fold',
                  live_claim='Local shadow replay and receipt instrumentation only; production mitigation effectiveness not verified'))
    paths=[Path(__file__),ROOT/'backend/app/models/warning_policy.py',ROOT/'backend/app/models/warning_profiles.py',ROOT/'backend/app/routers/live_router.py',
           ROOT/'backend/research/streaming_forecast.py',ROOT/'backend/research/benchmark_live.py',
           ROOT/'backend/tests/test_operational_improvements.py']
    report['source_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    if not __debug__:raise RuntimeError('Run this audit without Python optimization so all verification assertions execute')
    with threadpool_limits(limits=1):run()

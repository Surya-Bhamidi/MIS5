"""Frozen AIT-fold transfer diagnostic on complete CAM Wazuh streams."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json

import numpy as np
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingClassifier

import evidence_pilot as pilot
import extended_study as study
from prepare_extended_data import detector_token
from audit_endpoints import OUT,strict_warning_metrics
from fusion_study import logit

CAM=pilot.ROOT/'data/research/cam_lds'

def timestamp(value):
    parsed=datetime.fromisoformat(value)
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()

def prepare():
    manifests=json.loads((CAM/'manifest.json').read_text());episodes={};audit=[]
    for manifest in manifests:
        name=manifest['scenario'];folder=CAM/name
        for member in manifest['members']:
            if hashlib.sha256((pilot.ROOT/member['path']).read_bytes()).hexdigest()!=member['sha256']:
                raise ValueError('CAM checksum mismatch')
        execution=[json.loads(line) for line in (folder/'attackmate.json').read_text(encoding='utf-8').splitlines()]
        steps=[r for r in execution if 'Privilege Escalation' in
            (r['parameters'].get('metadata') or {}).get('tactics','')]
        reports=[];seen=set();sources=Counter()
        for line in (folder/'alerts.json').read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            # CAM stores native Wazuh timestamp; AIT stores its JSON-export alias.
            event['@timestamp']=event['timestamp']
            record=pilot.parse_record(event,0)
            if record is None or record[3] in seen:continue
            seen.add(record[3]);reports.append((record[0],detector_token(event,record[2])))
            sources[detector_token(event,record[2]).split(':')[0]]+=1
        first,last=min(r[0] for r in reports),max(r[0] for r in reports)
        annotation={'scenario':name,'reports':len(reports),'observed_sources':dict(sources),
            'first_report':first,'last_report':last,'recorded_hours':(last-first)/3600,
            'endpoint_status':'first executed privilege tactic; successful outcome not verified',
            'naive_attacker_times_interpreted_as':'UTC; checked against UTC Wazuh capture date/time',
            'missing_input_sources':sorted({'aminer','wazuh','suricata'}-set(sources)),
            'eligible':bool(steps)}
        if not steps:
            annotation['exclusion']='No published Privilege Escalation tactic in this template'
            audit.append(annotation);continue
        onset=min(timestamp(r['start-datetime']) for r in steps)
        annotation.update(onset=onset,pre_endpoint_minutes=(onset-first)/60,
                          negative_minutes_at_15=max(0,(onset-first)/60-15))
        if not first<onset<last:raise ValueError('Execution proxy outside source coverage')
        times=np.arange(np.ceil(first/60)*60+60,np.floor(last/60)*60+1,60)
        tokens=sorted({r[1] for r in reports});mapping={token:i for i,token in enumerate(tokens)}
        counts=np.zeros((len(times),len(tokens)));bins=defaultdict(Counter)
        for when,token in reports:
            index=np.searchsorted(times,when,side='left')
            if index<len(times):bins[int(index)][token]+=1
        for index,values in bins.items():
            for token,value in values.items():counts[index,mapping[token]]=value
        episodes[name]={'counts':counts,'names':np.array(tokens),'times':times,
                        'truth':np.zeros(len(times),dtype=int),'onset':onset}
        annotation['coverage_assumption']='Continuous collection between observed first and last report; no heartbeat verification'
        audit.append(annotation)
    return episodes,audit

def run():
    OUT.mkdir(parents=True,exist_ok=True);pilot.HORIZONS=study.HORIZONS
    transferred,audit=prepare();episodes=study.load('ait');episodes.update(transferred)
    test='fox';val='harrison';train=[n for n in pilot.SCENARIOS if n not in [test,val]]
    counts,vocab=study.aligned_counts(episodes,train);edges=study.count_edges(counts,train)
    symbols={n:study.symbols_for(counts[n],edges) for n in episodes}
    features={n:study.temporal_features(counts[n]) for n in episodes}
    model=study.fit_model(episodes,train,symbols);predict=[val]+list(transferred)
    duration={n:study.forecast(model,symbols[n],'duration_hmm') for n in predict}
    boosted={n:[] for n in predict}
    x=np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
    for h in study.HORIZONS:
        y=np.concatenate([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])] for n in train])
        estimator=HistGradientBoostingClassifier(max_iter=100,learning_rate=.08,max_leaf_nodes=15,
            min_samples_leaf=20,l2_regularization=1,early_stopping=False,random_state=1729)
        estimator.fit(x,y)
        for n in predict:boosted[n].append(estimator.predict_proba(features[n])[:,1])
    boosted={n:np.maximum.accumulate(np.stack(values,axis=1),axis=1) for n,values in boosted.items()}
    details=next(r for r in json.loads((study.OUT/'fusion_metadata.json').read_text()) if r['test']==test)
    fused={n:np.maximum.accumulate(np.stack([expit(np.stack([logit(duration[n][:,j]),logit(boosted[n][:,j])],axis=1)
        @np.array(details['meta_coefficients'][j])[0]+details['meta_intercepts'][j][0])
        for j in range(len(study.HORIZONS))],axis=1),axis=1) for n in predict}
    modes={'duration_hmm':duration,'temporal_boosting':boosted,'conditional_fusion':fused,
           'equal_fusion':{n:(duration[n]+boosted[n])/2 for n in predict}}
    differences={}
    for mode,values in modes.items():
        with np.load(study.OUT/'predictions'/f'ait_fox_{mode}.npz') as saved:
            difference=float(np.max(np.abs(values[val]-saved['validation_raw'])))
        if difference>1e-10:raise ValueError(f'Frozen base reconstruction failed: {mode}: {difference}')
        differences[mode]=difference
    original=json.loads((study.OUT/'ait_fold_results.json').read_text())+json.loads((study.OUT/'fusion_fold_results.json').read_text())
    rows=[];directory=OUT/'predictions';directory.mkdir(exist_ok=True)
    for mode,values in modes.items():
        thresholds=next(r for r in original if r['test']==test and r['mode']==mode)['calibrated']
        for n in transferred:
            _,p=pilot.calibrate(episodes[val],values[val],values[n])
            scores={}
            for j,h in enumerate(study.HORIZONS):
                metrics=strict_warning_metrics(episodes[n],p[:,j],h,thresholds[str(h)]['threshold'])
                mask=pilot.preonset(episodes[n]);y=pilot.targets(episodes[n],h)[mask]
                exposure=float(np.sum(y==0)/60)
                metrics['negative_exposure_hours']=exposure
                metrics['false_warnings_per_24h']=(metrics['false_warning_episodes']/exposure*24
                    if exposure>0 else None)
                metrics['brier']=float(np.mean((p[mask,j]-y)**2))
                scores[str(h)]=metrics
            rows.append({'scenario':n,'mode':mode,'scores':scores})
            np.savez_compressed(directory/f'cam_{n}_{mode}.npz',raw=values[n],calibrated=p,
                times=episodes[n]['times'],onset=episodes[n]['onset'],horizons=study.HORIZONS)
    result={'status':'missing-sensor/domain-shift diagnostic, execution-proxy endpoint',
        'frozen_fitting_campaigns':train,'frozen_validation_campaign':val,
        'reconstruction_max_errors':differences,'vocabulary':vocab,'source_audit':audit,'results':rows}
    (OUT/'cam_transfer.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'eligible_templates':len(transferred),'reconstruction_errors':differences,
        '15_minute_results':[{'scenario':r['scenario'],'mode':r['mode'],**r['scores']['15']} for r in rows]},indent=2),flush=True)

if __name__=='__main__':run()

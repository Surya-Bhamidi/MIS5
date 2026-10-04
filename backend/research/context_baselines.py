"""Clock and longer-history controls; not candidates selected into the pipeline."""
import json
import time

import numpy as np
from threadpoolctl import threadpool_limits

import evidence_pilot as pilot
import extended_study as study
from robust_forecasting import estimator
from run_robust_forecasting import OUT,score
from comparison_audit import select_threshold,BUDGETS
from audit_endpoints import OUT as VALIDATION

CONTEXT_MODES=['clock_only_boosting','long_history_boosting']

def context_features(x,times,mode):
    clock=np.log1p((times-times[0])/60).reshape(-1,1)
    if mode=='clock_only_boosting':return clock
    raw=np.log1p(x);sums=np.vstack([np.zeros((1,x.shape[1])),np.cumsum(raw,axis=0)])
    ends=np.arange(1,len(x)+1);parts=[study.temporal_features(x)]
    for size in [180,360,1440]:
        starts=np.maximum(0,ends-size);parts.append((sums[ends]-sums[starts])/(ends-starts)[:,None])
    return np.c_[np.concatenate(parts,axis=1),clock]

def run():
    OUT.mkdir(exist_ok=True);(OUT/'predictions').mkdir(exist_ok=True)
    pilot.HORIZONS=study.HORIZONS;episodes=study.load('ait');rows=[];folds=[];selected=[]
    roots={r['scenario']:r['successful_root'] for r in json.loads((VALIDATION/'endpoint_evidence.json').read_text())}
    for fold,test in enumerate(pilot.SCENARIOS):
        start=time.monotonic();val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in episodes if n not in [test,val]];counts,names=study.aligned_counts(episodes,train)
        for mode in CONTEXT_MODES:
            features={n:context_features(counts[n],episodes[n]['times'],mode) for n in episodes}
            xt=np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
            vp=[];tp=[]
            for h in study.HORIZONS:
                y=np.concatenate([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])] for n in train])
                model=estimator().fit(xt,y)
                vp.append(model.predict_proba(features[val])[:,1]);tp.append(model.predict_proba(features[test])[:,1])
            vp=np.maximum.accumulate(np.stack(vp,axis=1),axis=1);tp=np.maximum.accumulate(np.stack(tp,axis=1),axis=1)
            cvp,cp=pilot.calibrate(episodes[val],vp,tp)
            np.savez_compressed(OUT/'predictions'/f'ait_{test}_{mode}.npz',raw=tp,calibrated=cp,
                validation_raw=vp,validation_calibrated=cvp,times=episodes[test]['times'],onset=episodes[test]['onset'],horizons=study.HORIZONS)
            row={'test':test,'validation':val,'train':train,'mode':mode,'feature_columns':features[test].shape[1]}
            for label,v,p in [('raw',vp,tp),('calibrated',cvp,cp)]:
                row[label]={str(h):score(episodes[test],p[:,j],h,select_threshold(episodes[val],v[:,j],h,1)) for j,h in enumerate(study.HORIZONS)}
            folds.append(row)
            for j,h in enumerate(study.HORIZONS):
                for budget in BUDGETS:
                    threshold=select_threshold(episodes[val],cvp[:,j],h,budget)
                    selected.append({'test':test,'validation':val,'mode':mode,'horizon':h,'budget':budget,
                        'threshold':threshold,'validation_metrics':score(episodes[val],cvp[:,j],h,threshold)})
                    for endpoint,onset in [('scheduled_onset',episodes[test]['onset']),('successful_root',roots[test])]:
                        ep={**episodes[test],'onset':onset}
                        rows.append({'scenario':test,'mode':mode,'endpoint':endpoint,'horizon':h,'budget':budget,**score(ep,cp[:,j],h,threshold)})
        for name,data in [('context_scored.json',rows),('context_folds.json',folds),('context_thresholds.json',selected)]:
            (OUT/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(f'Context controls {fold+1}/8 {test}: {time.monotonic()-start:.1f}s',flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=2):run()

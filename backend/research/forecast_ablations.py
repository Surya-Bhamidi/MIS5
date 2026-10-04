"""Fixed-setting feature ablations; no tuning or replacement of the candidate."""
import json
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import evidence_pilot as pilot
import extended_study as study


def run():
    pilot.HORIZONS=study.HORIZONS
    episodes=study.load('ait');results=[]
    for fold,test in enumerate(episodes):
        start=time.monotonic();val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in episodes if n not in [val,test]]
        counts,names=study.aligned_counts(episodes,train)
        for mode in ['boosting_current_only','boosting_only_aminer','boosting_only_suricata','boosting_only_wazuh']:
            if mode=='boosting_current_only':
                features={n:np.log1p(x) for n,x in counts.items()}
            else:
                sensor=mode.replace('boosting_only_','')
                columns=[n.startswith(sensor+':') for n in names]
                features={n:study.temporal_features(x[:,columns]) for n,x in counts.items()}
            x=np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
            vp,tp=[],[]
            for h in study.HORIZONS:
                y=np.concatenate([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])] for n in train])
                estimator=HistGradientBoostingClassifier(max_iter=100,learning_rate=.08,max_leaf_nodes=15,
                    min_samples_leaf=20,l2_regularization=1,early_stopping=False,random_state=1729)
                estimator.fit(x,y)
                vp.append(estimator.predict_proba(features[val])[:,1]);tp.append(estimator.predict_proba(features[test])[:,1])
            vp=np.maximum.accumulate(np.stack(vp,axis=1),axis=1)
            tp=np.maximum.accumulate(np.stack(tp,axis=1),axis=1)
            cvp,cp=pilot.calibrate(episodes[val],vp,tp)
            result={'dataset':'ait','test':test,'validation':val,'train':train,'mode':mode,
                    'threshold_source':'held-out validation','ablation':True}
            for label,validation,prediction in [('raw',vp,tp),('calibrated',cvp,cp)]:
                thresholds=[study.choose_threshold(episodes[val],validation[:,j],h) for j,h in enumerate(study.HORIZONS)]
                result[label],result[label+'_decisions'],result[label+'_fixed_thresholds']=study.score(episodes[test],prediction,thresholds)
            results.append(result)
            np.savez_compressed(study.OUT/'predictions'/f'ait_{test}_{mode}.npz',raw=tp,calibrated=cp,
                validation_raw=vp,validation_calibrated=cvp,times=episodes[test]['times'],onset=episodes[test]['onset'],horizons=study.HORIZONS)
        (study.OUT/'ablation_fold_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(f'Feature ablations {fold+1}/8 {test} ({time.monotonic()-start:.1f}s)',flush=True)


if __name__=='__main__':
    run()

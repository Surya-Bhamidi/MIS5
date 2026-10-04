"""Equal-input full-sensor-outage stress; altered campaigns are not new samples."""
import argparse
import json
import time

import numpy as np
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

import extended_study as study
import evidence_pilot as pilot
from fusion_study import logit


def run(dataset):
    pilot.HORIZONS=study.HORIZONS
    episodes=study.load(dataset)
    original=json.loads((study.OUT/f"{dataset}_fold_results.json").read_text())
    fusion=[]
    if dataset=="ait":
        fusion=json.loads((study.OUT/"fusion_fold_results.json").read_text())
        meta={r['test']:r for r in json.loads((study.OUT/"fusion_metadata.json").read_text())}
    results=[]
    for fold,test in enumerate(episodes):
        start=time.monotonic()
        reference={r['mode']:r for r in original+fusion if r['test']==test}
        train=reference['duration_hmm']['train'];val=reference['duration_hmm']['validation']
        counts,names=study.aligned_counts(episodes,train)
        edges=study.count_edges(counts,train)
        symbols={n:study.symbols_for(x,edges) for n,x in counts.items()}
        model=study.fit_model(episodes,train,symbols)
        features={n:study.temporal_features(x) for n,x in counts.items()}
        xt=np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
        estimators={}
        for mode in study.MODES[3:]:
            estimators[mode]=[]
            for h in study.HORIZONS:
                y=np.concatenate([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])] for n in train])
                estimator=(LogisticRegression(C=1,max_iter=1000) if mode=='temporal_logistic' else
                    HistGradientBoostingClassifier(max_iter=100,learning_rate=.08,max_leaf_nodes=15,
                    min_samples_leaf=20,l2_regularization=1,early_stopping=False,random_state=1729))
                estimator.fit(xt,y);estimators[mode].append(estimator)
        for sensor in sorted(set(n.split(':')[0] for n in names)):
            dropped=counts[test].copy()
            dropped[:,[n.startswith(sensor+':') for n in names]]=0
            ds=study.symbols_for(dropped,edges);df=study.temporal_features(dropped)
            raw={mode:study.forecast(model,ds,mode) for mode in study.MODES[:3]}
            for mode,models in estimators.items():
                raw[mode]=np.maximum.accumulate(np.stack([m.predict_proba(df)[:,1] for m in models],axis=1),axis=1)
                # Refitting on exactly the original split must reproduce natural risk.
                natural=np.maximum.accumulate(np.stack([m.predict_proba(features[test])[:,1] for m in models],axis=1),axis=1)
                with np.load(study.OUT/'predictions'/f'{dataset}_{test}_{mode}.npz') as saved:
                    assert np.allclose(natural,saved['raw'],atol=1e-10), (test,mode)
            if dataset=='ait':
                raw['equal_fusion']=(raw['duration_hmm']+raw['temporal_boosting'])/2
                coefficients=meta[test]['meta_coefficients'];intercepts=meta[test]['meta_intercepts']
                raw['conditional_fusion']=np.maximum.accumulate(np.stack([
                    expit(np.stack([logit(raw['duration_hmm'][:,j]),logit(raw['temporal_boosting'][:,j])],axis=1) @
                    np.array(coefficients[j][0])+intercepts[j][0]) for j in range(len(study.HORIZONS))],axis=1),axis=1)
            for mode,prediction in raw.items():
                with np.load(study.OUT/'predictions'/f'{dataset}_{test}_{mode}.npz') as saved:
                    vp=saved['validation_raw'].copy()
                _,calibrated=pilot.calibrate(episodes[val],vp,prediction) if dataset=='ait' else (vp,prediction)
                thresholds=[reference[mode]['calibrated'][str(h)]['threshold'] for h in study.HORIZONS]
                scores,decisions,fixed=study.score(episodes[test],calibrated,thresholds)
                results.append({'dataset':dataset,'test':test,'mode':mode,'dropped_sensor':sensor,
                    'threshold_source':'unchanged natural validation','calibrated':scores,
                    'calibrated_decisions':decisions,'calibrated_fixed_thresholds':fixed})
        (study.OUT/f'{dataset}_sensor_stress.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(f'Sensor stress {dataset} {fold+1}/{len(episodes)} {test} ({time.monotonic()-start:.1f}s)',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('dataset',choices=['ait','darpa'])
    run(parser.parse_args().dataset)

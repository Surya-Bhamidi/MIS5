"""Cross-fitted conditional forecast fusion; deliberately labeled exploratory."""
import json
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

import extended_study as study
import evidence_pilot as pilot


def logit(p):
    p=np.clip(p,1e-8,1-1e-8)
    return np.log(p/(1-p))


def fit_predict(episodes,train,predict):
    counts,names=study.aligned_counts(episodes,train)
    edges=study.count_edges(counts,train)
    symbols={n:study.symbols_for(counts[n],edges) for n in episodes}
    features={n:study.temporal_features(counts[n]) for n in episodes}
    model=study.fit_model(episodes,train,symbols)
    predictions={n:[study.forecast(model,symbols[n],"duration_hmm"),[]] for n in predict}
    x=np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
    for horizon in study.HORIZONS:
        y=np.concatenate([pilot.targets(episodes[n],horizon)[pilot.preonset(episodes[n])] for n in train])
        estimator=HistGradientBoostingClassifier(max_iter=100,learning_rate=.08,max_leaf_nodes=15,
            min_samples_leaf=20,l2_regularization=1,early_stopping=False,random_state=1729)
        estimator.fit(x,y)
        for n in predict:
            predictions[n][1].append(estimator.predict_proba(features[n])[:,1])
    for n in predictions:
        predictions[n][1]=np.maximum.accumulate(np.stack(predictions[n][1],axis=1),axis=1)
    return predictions


def run():
    pilot.HORIZONS=study.HORIZONS
    episodes=study.load("ait")
    results=[]
    metadata=[]
    for fold,test in enumerate(episodes):
        start=time.monotonic()
        val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in episodes if n not in [test,val]]
        inner={}
        for fitting,predict in [(train[:3],train[3:]),(train[3:],train[:3])]:
            assert not set(fitting)&set(predict)
            inner.update(fit_predict(episodes,fitting,predict))
        meta_models=[]
        for j,h in enumerate(study.HORIZONS):
            x=np.concatenate([np.stack([logit(inner[n][0][:,j]),logit(inner[n][1][:,j])],axis=1)[pilot.preonset(episodes[n])] for n in train])
            y=np.concatenate([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])] for n in train])
            estimator=LogisticRegression(C=1,max_iter=1000)
            estimator.fit(x,y)
            meta_models.append(estimator)
        # Reuse saved full-fitting predictions from the completed extended study.
        predictions={}
        for n,label in [(val,"validation_raw"),(test,"raw")]:
            pairs=[]
            for mode in ["duration_hmm","temporal_boosting"]:
                with np.load(study.OUT/"predictions"/f"ait_{test}_{mode}.npz") as item:
                    pairs.append(item[label].copy())
            predictions[n]=pairs
        modes={"conditional_fusion":{},"equal_fusion":{}}
        for n,(duration,boosted) in predictions.items():
            modes["conditional_fusion"][n]=np.maximum.accumulate(np.stack([
                model.predict_proba(np.stack([logit(duration[:,j]),logit(boosted[:,j])],axis=1))[:,1]
                for j,model in enumerate(meta_models)],axis=1),axis=1)
            modes["equal_fusion"][n]=(duration+boosted)/2
        for mode,predicted in modes.items():
            vp,tp=predicted[val],predicted[test]
            cvp,cp=pilot.calibrate(episodes[val],vp,tp)
            result={"dataset":"ait","test":test,"validation":val,"train":train,"mode":mode,
                    "threshold_source":"held-out validation"}
            for label,validation,prediction in [("raw",vp,tp),("calibrated",cvp,cp)]:
                thresholds=[study.choose_threshold(episodes[val],validation[:,j],h) for j,h in enumerate(study.HORIZONS)]
                result[label],result[label+"_decisions"],result[label+"_fixed_thresholds"]=study.score(episodes[test],prediction,thresholds)
            results.append(result)
            np.savez_compressed(study.OUT/"predictions"/f"ait_{test}_{mode}.npz",raw=tp,calibrated=cp,
                validation_raw=vp,validation_calibrated=cvp,times=episodes[test]["times"],onset=episodes[test]["onset"],horizons=study.HORIZONS)
        metadata.append({"test":test,"train":train,"inner_folds":[[train[:3],train[3:]],[train[3:],train[:3]]],
                         "meta_coefficients":[m.coef_.tolist() for m in meta_models],
                         "meta_intercepts":[m.intercept_.tolist() for m in meta_models]})
        (study.OUT/"fusion_fold_results.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
        print(f"Cross-fitted fusion {fold+1}/8 {test} completed ({time.monotonic()-start:.1f}s)",flush=True)
    (study.OUT/"fusion_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    for mode in modes:
        rows=[r for r in results if r["mode"]==mode]
        print(mode,json.dumps({h:{"brier":float(np.mean([r['calibrated'][h]['brier'] for r in rows])),
            "ap":float(np.mean([r['calibrated'][h]['average_precision'] for r in rows])),
            "warned":sum(r['calibrated'][h]['warning_recall'] for r in rows),
            "false":sum(r['calibrated'][h]['false_warning_episodes'] for r in rows)} for h in ['5','15','30']}),flush=True)


if __name__=="__main__":
    run()

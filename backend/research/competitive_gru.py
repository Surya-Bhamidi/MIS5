"""Validation-selected training sensitivity; no claim of published-system replica."""
import copy
import json
import time

import numpy as np
import torch
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

import evidence_pilot as pilot
import extended_study as study
from gru_baseline import ForecastGRU, windows, infer, WINDOW
from audit_endpoints import strict_warning_metrics

OUT=pilot.ROOT/'experiments/published_comparison'
MODE='validation_selected_gru'
CHECKPOINTS=(6,12,18)

def fit_predict(episodes,train,validation,test):
    torch.set_num_threads(2);torch.manual_seed(1729)
    torch.use_deterministic_algorithms(True)
    counts,names=study.aligned_counts(episodes,train)
    raw={n:study.temporal_features(counts[n]) for n in train+[validation,test]}
    scaler=StandardScaler().fit(np.concatenate([raw[n] for n in train]))
    features={n:scaler.transform(raw[n]).astype(np.float32) for n in raw}
    indexes=np.concatenate([np.stack([np.full(pilot.preonset(episodes[n]).sum(),i),
        np.flatnonzero(pilot.preonset(episodes[n]))],axis=1) for i,n in enumerate(train)])
    labels=np.concatenate([np.stack([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])]
        for h in study.HORIZONS],axis=1) for n in train]).astype(np.float32)
    rng=np.random.default_rng(1729)
    positive=np.flatnonzero(labels[:,-1]>0);negative=np.flatnonzero(labels[:,-1]==0)
    selected=np.r_[positive,rng.choice(negative,min(10000,len(negative)),replace=False)]
    indexes=indexes[selected];labels=labels[selected]
    prevalence=labels.mean(axis=0)
    weights=np.sqrt((1-prevalence)/np.clip(prevalence,1e-6,1)).astype(np.float32)
    model=ForecastGRU(features[train[0]].shape[1])
    optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    criterion=torch.nn.BCEWithLogitsLoss(pos_weight=torch.from_numpy(weights))
    losses=[];candidates=[];best=None;chosen=None;chosen_vp=None;chosen_state=None
    for epoch in range(1,max(CHECKPOINTS)+1):
        model.train();order=rng.permutation(len(indexes));total=0.
        for start in range(0,len(order),128):
            selected=order[start:start+128];locations=indexes[selected]
            batch=np.empty((len(selected),WINDOW,features[train[0]].shape[1]),dtype=np.float32)
            for i,n in enumerate(train):
                mask=locations[:,0]==i
                if np.any(mask):batch[mask]=windows(features[n],locations[mask,1])
            optimizer.zero_grad();logits=model(torch.from_numpy(batch))
            loss=criterion(logits,torch.from_numpy(labels[selected]));loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
            total+=loss.item()*len(selected)
        losses.append(total/len(indexes))
        if epoch in CHECKPOINTS:
            vp=infer(model,features[validation]);mask=pilot.preonset(episodes[validation])
            ap={str(h):float(average_precision_score(pilot.targets(episodes[validation],h)[mask],
                vp[mask,study.HORIZONS.index(h)])) for h in [15,30]}
            value=float(np.mean(list(ap.values())));candidates.append({'epoch':epoch,'validation_ap':ap,'selection_score':value})
            if best is None or value>best:
                best=value;chosen=epoch;chosen_vp=vp.copy();chosen_state=copy.deepcopy(model.state_dict())
    model.load_state_dict(chosen_state)
    # Never evaluate the test sequence while choosing an epoch.
    tp=infer(model,features[test])
    probe=features[validation][:40]
    prefix_error=float(np.max(np.abs(infer(model,probe)[:17]-infer(model,probe[:17]))))
    assert prefix_error<1e-7
    return chosen_vp,tp,{'selected_epoch':chosen,'candidates':candidates,'training_loss':losses,
        'train_bins':len(indexes),'feature_columns':features[train[0]].shape[1],
        'vocabulary':names,'prefix_max_error':prefix_error,'seed':1729,
        'selection_source':'validation only; shared with calibration/threshold selection',
        'test_inference':'only after selecting checkpoint'}

def run():
    pilot.HORIZONS=study.HORIZONS;episodes=study.load('ait');rows=[];metadata=[]
    (OUT/'predictions').mkdir(parents=True,exist_ok=True)
    for fold,test in enumerate(episodes):
        start=time.monotonic();val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in episodes if n not in [val,test]]
        vp,tp,details=fit_predict(episodes,train,val,test)
        cvp,cp=pilot.calibrate(episodes[val],vp,tp)
        row={'dataset':'ait','test':test,'validation':val,'train':train,'mode':MODE,
            'status':'bounded same-task training sensitivity, not Ansari2022 reproduction'}
        for label,v,p in [('raw',vp,tp),('calibrated',cvp,cp)]:
            thresholds=[study.choose_threshold(episodes[val],v[:,j],h) for j,h in enumerate(study.HORIZONS)]
            row[label],_,_=study.score(episodes[test],p,thresholds)
            for j,h in enumerate(study.HORIZONS):row[label][str(h)].update(strict_warning_metrics(episodes[test],p[:,j],h,thresholds[j]))
        rows.append(row);metadata.append({'test':test,'validation':val,'train':train,**details})
        np.savez_compressed(OUT/'predictions'/f'ait_{test}_{MODE}.npz',raw=tp,calibrated=cp,
            validation_raw=vp,validation_calibrated=cvp,times=episodes[test]['times'],
            onset=episodes[test]['onset'],horizons=study.HORIZONS)
        (OUT/'gru_fold_results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        (OUT/'gru_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print(f'Validation-selected GRU {fold+1}/8 {test}: epoch {details["selected_epoch"]}, {time.monotonic()-start:.1f}s',flush=True)

if __name__=='__main__':run()

"""Bounded three-layer GRU adaptation; not a Warden paper reproduction."""
import argparse
import json
import time

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

import evidence_pilot as pilot
import extended_study as study
from audit_endpoints import OUT,strict_warning_metrics

WINDOW=30

class ForecastGRU(torch.nn.Module):
    def __init__(self,columns):
        super().__init__()
        self.gru=torch.nn.GRU(columns,32,num_layers=3,batch_first=True,dropout=0)
        self.head=torch.nn.Linear(32,len(study.HORIZONS))
    def forward(self,x):
        sequence,_=self.gru(x)
        return self.head(sequence[:,-1])

def windows(features,ends):
    padded=np.vstack([np.zeros((WINDOW-1,features.shape[1]),dtype=np.float32),features])
    return padded[ends[:,None]+np.arange(WINDOW)[None,:]]

def infer(model,x):
    model.eval();p=[]
    with torch.no_grad():
        for start in range(0,len(x),256):
            sample=windows(x,np.arange(start,min(start+256,len(x))))
            p.append(torch.sigmoid(model(torch.from_numpy(sample))).numpy())
    # Score/calibrate in float64 consistently with the non-neural comparators.
    return np.maximum.accumulate(np.concatenate(p).astype(np.float64),axis=1)

def fit_predict(episodes,train,predict):
    torch.set_num_threads(2);torch.manual_seed(1729)
    torch.use_deterministic_algorithms(True)
    counts,names=study.aligned_counts(episodes,train)
    scaler=StandardScaler().fit(np.concatenate([np.log1p(counts[n]) for n in train]))
    features={n:scaler.transform(np.log1p(counts[n])).astype(np.float32) for n in train+predict}
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
    model=ForecastGRU(len(names));optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    criterion=torch.nn.BCEWithLogitsLoss(pos_weight=torch.from_numpy(weights))
    losses=[]
    for epoch in range(6):
        model.train();order=rng.permutation(len(indexes));total=0.
        for start in range(0,len(order),128):
            chosen=order[start:start+128];locations=indexes[chosen]
            batch=np.empty((len(chosen),WINDOW,len(names)),dtype=np.float32)
            for i,n in enumerate(train):
                mask=locations[:,0]==i
                if np.any(mask):batch[mask]=windows(features[n],locations[mask,1])
            optimizer.zero_grad();logits=model(torch.from_numpy(batch))
            loss=criterion(logits,torch.from_numpy(labels[chosen]));loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
            total+=loss.item()*len(chosen)
        losses.append(total/len(indexes))
    return {n:infer(model,features[n]) for n in predict},{'vocabulary':names,'training_loss':losses,
        'training_bins':len(indexes),'positive_bins':labels.sum(axis=0).tolist(),
        'bce_positive_weights':weights.tolist(),'torch':torch.__version__,'seed':1729}

def checks():
    torch.set_num_threads(2);torch.manual_seed(1729)
    x=np.arange(180,dtype=np.float32).reshape(60,3)/100
    model=ForecastGRU(3)
    p=infer(model,x)
    assert np.array_equal(windows(x,np.array([0]))[0,-1],x[0])
    assert np.allclose(p[:10],infer(model,x[:10]),atol=1e-7)
    assert np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=0)
    print('GRU checks passed: past-only windows, prefix-invariant forecasts, probability bounds and horizon coherence',flush=True)

def run():
    checks();pilot.HORIZONS=study.HORIZONS
    episodes=study.load('ait');rows=[];metadata=[];mode='ansari2022_adapted_gru'
    directory=OUT/'predictions';directory.mkdir(parents=True,exist_ok=True)
    for fold,test in enumerate(episodes):
        start=time.monotonic();val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in episodes if n not in [test,val]]
        prediction,details=fit_predict(episodes,train,[val,test]);vp,tp=prediction[val],prediction[test]
        cvp,cp=pilot.calibrate(episodes[val],vp,tp)
        row={'dataset':'ait','test':test,'validation':val,'train':train,'mode':mode,
             'status':'method adaptation, not paper result reproduction'}
        for label,validation,p in [('raw',vp,tp),('calibrated',cvp,cp)]:
            thresholds=[study.choose_threshold(episodes[val],validation[:,j],h) for j,h in enumerate(study.HORIZONS)]
            row[label],_,_=study.score(episodes[test],p,thresholds)
            for j,h in enumerate(study.HORIZONS):row[label][str(h)].update(strict_warning_metrics(episodes[test],p[:,j],h,thresholds[j]))
        rows.append(row);metadata.append({'test':test,'validation':val,'train':train,**details})
        np.savez_compressed(directory/f'ait_{test}_{mode}.npz',raw=tp,calibrated=cp,
            validation_raw=vp,validation_calibrated=cvp,times=episodes[test]['times'],
            onset=episodes[test]['onset'],horizons=study.HORIZONS)
        (OUT/'gru_fold_results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        (OUT/'gru_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print(f'GRU adaptation {fold+1}/8 {test}: {time.monotonic()-start:.1f}s',flush=True)
    print(json.dumps({str(h):{'brier':float(np.mean([r['calibrated'][str(h)]['brier'] for r in rows])),
        'ap':float(np.mean([r['calibrated'][str(h)]['average_precision'] for r in rows])),
        'warned':sum(r['calibrated'][str(h)]['warning_recall'] for r in rows),
        'strict_warned':sum(r['calibrated'][str(h)]['strict_warning_recall'] for r in rows),
        'false':sum(r['calibrated'][str(h)]['false_warning_episodes'] for r in rows)} for h in [5,15,30]}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--checks',action='store_true');args=parser.parse_args()
    checks() if args.checks else run()

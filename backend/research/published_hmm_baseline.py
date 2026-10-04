"""Explicit clock-time adaptation of Perera et al., arXiv:1610.07276.

Preserves clustered observations, Baum-Welch, and prefix-Viterbi decoding.
Changes the input representation and adds a target-hazard adapter. These scores
are not a reproduction of the original next-alert/Snort experiment.
"""
import argparse
import hashlib
import json
import time

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

import evidence_pilot as pilot
import extended_study as study
from audit_endpoints import OUT, strict_warning_metrics

def forward(observations,a,b,pi):
    length=len(observations);states=len(pi)
    alpha=np.zeros((length,states));scales=np.zeros(length)
    alpha[0]=pi*b[:,observations[0]]
    scales[0]=alpha[0].sum();alpha[0]/=scales[0]
    for t in range(1,length):
        alpha[t]=(alpha[t-1]@a)*b[:,observations[t]]
        scales[t]=alpha[t].sum();alpha[t]/=scales[t]
    return alpha,scales

def expected_counts(observations,a,b,pi):
    alpha,scales=forward(observations,a,b,pi)
    states=len(pi);length=len(observations)
    beta=np.ones((length,states))
    for t in range(length-2,-1,-1):
        beta[t]=a@(b[:,observations[t+1]]*beta[t+1])/scales[t+1]
    gamma=alpha*beta
    gamma/=gamma.sum(axis=1,keepdims=True)
    right=b[:,observations[1:]].T*beta[1:]/scales[1:,None]
    ac=a*(alpha[:-1].T@right)
    bc=np.stack([np.bincount(observations,weights=gamma[:,state],minlength=b.shape[1])
                 for state in range(states)])
    return ac,bc,gamma[0],np.log(scales).sum()

def fit_hmm(sequences,states=8,clusters=10,iterations=25):
    rng=np.random.default_rng(1729)
    a=rng.uniform(.1,1,(states,states))+np.eye(states)*10
    b=rng.uniform(.1,1,(states,clusters));pi=np.ones(states)/states
    a/=a.sum(axis=1,keepdims=True);b/=b.sum(axis=1,keepdims=True)
    history=[]
    for _ in range(iterations):
        ac=np.full_like(a,.01);bc=np.full_like(b,.01);pc=np.full_like(pi,.01);ll=0.
        for seq in sequences:
            ta,tb,tp,value=expected_counts(np.ascontiguousarray(seq),a,b,pi)
            ac+=ta;bc+=tb;pc+=tp;ll+=value
        history.append(float(ll))
        a=ac/ac.sum(axis=1,keepdims=True);b=bc/bc.sum(axis=1,keepdims=True);pi=pc/pc.sum()
    return {'a':a,'b':b,'pi':pi,'likelihood_history':history}

def viterbi_prefix(observations,a,b,pi):
    length=len(observations);states=len(pi)
    posterior=np.zeros((length,states))
    delta=np.log(pi)+np.log(b[:,observations[0]])
    posterior[0,np.argmax(delta)]=1.
    loga=np.log(a);logb=np.log(b)
    for t in range(1,length):
        nxt=np.max(delta[:,None]+loga,axis=0)+logb[:,observations[t]]
        delta=nxt-np.max(nxt)
        posterior[t,np.argmax(delta)]=1.
    return posterior

def first_onset_projection(model,observations,hazard,mode):
    belief=(viterbi_prefix(observations,model['a'],model['b'],model['pi']) if mode=='viterbi'
        else forward(observations,model['a'],model['b'],model['pi'])[0])
    # Target occurs before the next latent-state transition: Q_ij=(1-lambda_i) A_ij.
    q=(1-hazard[:,None])*model['a']
    survivor=np.ones(len(hazard));columns=[]
    for minute in range(1,max(study.HORIZONS)+1):
        survivor=q@survivor
        if minute in study.HORIZONS:columns.append(1-survivor)
    return np.clip(belief@np.stack(columns,axis=1),0,1)

def fit_predict(episodes,train,predict):
    counts,vocabulary=study.aligned_counts(episodes,train)
    fitting=np.concatenate([np.log1p(counts[n]) for n in train])
    scaler=StandardScaler().fit(fitting)
    selected=np.linspace(0,len(fitting)-1,min(10000,len(fitting)),dtype=int)
    cluster=KMeans(n_clusters=10,n_init=3,max_iter=300,random_state=1729)
    cluster.fit(scaler.transform(fitting[selected]))
    observations={n:np.ascontiguousarray(cluster.predict(scaler.transform(np.log1p(counts[n]))).astype(np.int64))
                  for n in train+predict}
    model=fit_hmm([observations[n] for n in train])
    numerator=np.full(8,.01);denominator=np.full(8,.02)
    for n in train:
        mask=pilot.preonset(episodes[n])
        belief=forward(observations[n],model['a'],model['b'],model['pi'])[0][mask]
        numerator+=belief.T@pilot.targets(episodes[n],1)[mask]
        denominator+=belief.sum(axis=0)
    hazard=numerator/denominator
    predictions={mode:{n:first_onset_projection(model,observations[n],hazard,mode) for n in predict}
                 for mode in ['viterbi','filtered']}
    metadata={'vocabulary':vocabulary,'likelihood_history':model['likelihood_history'],
              'a':model['a'].tolist(),'b':model['b'].tolist(),'pi':model['pi'].tolist(),
              'target_hazard':hazard.tolist(),'kmeans_centers':cluster.cluster_centers_.tolist(),
              'feature_mean':scaler.mean_.tolist(),'feature_scale':scaler.scale_.tolist(),
              'fitting_bins':len(fitting),'kmeans_fitting_bins':len(selected)}
    return predictions,metadata

def checks():
    sequences=[np.array([0,0,0,1,1,2,2,2,0],dtype=np.int64),np.array([1,1,2,2,0,0],dtype=np.int64)]
    model=fit_hmm(sequences,states=3,clusters=3,iterations=8)
    assert np.allclose(model['a'].sum(axis=1),1) and np.allclose(model['b'].sum(axis=1),1)
    assert model['likelihood_history'][-1]>model['likelihood_history'][0]
    seq=sequences[0];hazard=np.array([.01,.1,.5])
    for mode in ['viterbi','filtered']:
        p=first_onset_projection(model,seq,hazard,mode)
        assert np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
        assert np.allclose(p[:4],first_onset_projection(model,seq[:4],hazard,mode))
        assert np.allclose(first_onset_projection(model,seq,np.zeros(3),mode),0)
    print('Adapted HMM checks passed: EM improvement, stochastic rows, causal prefix decoding, coherent first-onset risk',flush=True)

def run():
    checks();pilot.HORIZONS=study.HORIZONS
    episodes=study.load('ait');rows=[];metadata=[]
    directory=OUT/'predictions';directory.mkdir(parents=True,exist_ok=True)
    for fold,test in enumerate(episodes):
        start=time.monotonic();val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in episodes if n not in [test,val]]
        predictions,details=fit_predict(episodes,train,[val,test])
        for decoding,values in predictions.items():
            mode='perera2016_adapted_'+decoding;vp,tp=values[val],values[test]
            cvp,cp=pilot.calibrate(episodes[val],vp,tp)
            result={'dataset':'ait','test':test,'validation':val,'train':train,'mode':mode,
                'status':'method adaptation, not paper result reproduction'}
            for label,validation,prediction in [('raw',vp,tp),('calibrated',cvp,cp)]:
                thresholds=[study.choose_threshold(episodes[val],validation[:,j],h) for j,h in enumerate(study.HORIZONS)]
                result[label],_,_=study.score(episodes[test],prediction,thresholds)
                for j,h in enumerate(study.HORIZONS):
                    result[label][str(h)].update(strict_warning_metrics(episodes[test],prediction[:,j],h,thresholds[j]))
            rows.append(result)
            np.savez_compressed(directory/f'ait_{test}_{mode}.npz',raw=tp,calibrated=cp,
                validation_raw=vp,validation_calibrated=cvp,times=episodes[test]['times'],
                onset=episodes[test]['onset'],horizons=study.HORIZONS)
        metadata.append({'test':test,'validation':val,'train':train,**details})
        (OUT/'published_hmm_fold_results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        (OUT/'published_hmm_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print(f'Published HMM adaptation {fold+1}/8 {test}: {time.monotonic()-start:.1f}s',flush=True)
    for mode in sorted({r['mode'] for r in rows}):
        subset=[r for r in rows if r['mode']==mode]
        print(mode,json.dumps({str(h):{'brier':float(np.mean([r['calibrated'][str(h)]['brier'] for r in subset])),
            'ap':float(np.mean([r['calibrated'][str(h)]['average_precision'] for r in subset])),
            'warned':sum(r['calibrated'][str(h)]['warning_recall'] for r in subset),
            'strict_warned':sum(r['calibrated'][str(h)]['strict_warning_recall'] for r in subset),
            'false':sum(r['calibrated'][str(h)]['false_warning_episodes'] for r in subset)} for h in [5,15,30]}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--checks',action='store_true');args=parser.parse_args()
    checks() if args.checks else run()

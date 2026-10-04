"""Availability-aware BN/HMM state features for causal attack-onset forecasts."""
from itertools import combinations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import extended_study as study
import evidence_pilot as pilot

SENSORS=('aminer','suricata','wazuh')
SUBSETS=[tuple(SENSORS)]+[s for size in [2,1] for s in combinations(SENSORS,size)]

def subset_key(available):
    available=tuple(sorted(set(available)))
    if not set(available)<=set(SENSORS):raise ValueError('Unknown detector family')
    return '+'.join(available) or 'none'

def present_columns(names,available):
    subset_key(available)
    return np.array([i for i,n in enumerate(names) if n.split(':')[0] in available],dtype=int)

def align(ep,names):
    mapping={n:i for i,n in enumerate(names)}
    x=np.zeros((len(ep['times']),len(names)))
    for j,token in enumerate(ep['names']):
        token=str(token);key=token if token in mapping else token.split(':')[0]+':OTHER'
        if key in mapping:x[:,mapping[key]]+=ep['counts'][:,j]
    return x

def state_filter(model,symbols,columns):
    """Past-only HMM update using tempered BN likelihood of observed children."""
    ll=np.zeros((len(symbols),len(model['pi'])))
    for j in columns:ll+=np.log(model['b'][:,j,symbols[:,j]].T)
    if len(columns):ll/=np.sqrt(len(columns))
    belief=model['pi'].copy();result=np.empty_like(ll)
    for t,values in enumerate(ll):
        prior=belief@model['a']
        logits=np.log(np.clip(prior,1e-300,1))+values
        logits-=np.max(logits);belief=np.exp(logits);belief/=belief.sum()
        result[t]=belief
    return result

def stage_features(belief):
    # Same trailing-mean operator, applied to state probabilities (without log).
    sums=np.vstack([np.zeros((1,belief.shape[1])),np.cumsum(belief,axis=0)])
    ends=np.arange(1,len(belief)+1);parts=[belief]
    for size in [5,15,60]:
        starts=np.maximum(0,ends-size)
        parts.append((sums[ends]-sums[starts])/(ends-starts)[:,None])
    return np.concatenate(parts,axis=1)

def fit_state(episodes,counts,train):
    edges=study.count_edges(counts,train)
    symbols={n:study.symbols_for(counts[n],edges) for n in train}
    return study.fit_model(episodes,train,symbols),edges

def crossfit_states(episodes,counts,names,train,predict,available,state_cache=None):
    columns=present_columns(names,available);values={};splits=[]
    state_cache={} if state_cache is None else state_cache
    def fitted(fitting):
        key=tuple(fitting)
        if key not in state_cache:state_cache[key]=fit_state(episodes,counts,fitting)
        return state_cache[key]
    for n in train:
        fitting=[m for m in train if m!=n]
        model,edges=fitted(fitting)
        values[n]=state_filter(model,study.symbols_for(counts[n],edges),columns)
        splits.append({'prediction_campaign':n,'fitting_campaigns':fitting})
    model,edges=fitted(train)
    for n in predict:values[n]=state_filter(model,study.symbols_for(counts[n],edges),columns)
    return values,splits,model,edges

def estimator():
    return HistGradientBoostingClassifier(max_iter=100,learning_rate=.08,max_leaf_nodes=15,
        min_samples_leaf=20,l2_regularization=1,early_stopping=False,random_state=1729)

def blend_predictions(base,augmented,weight):
    if not 0<=weight<=1:raise ValueError('Blend weight out of bounds')
    return (1-weight)*base+weight*augmented

def select_blend(ep,validation_candidates,weights):
    """Selection depends on validation forecasts and labels only."""
    mask=pilot.preonset(ep)
    y=np.stack([pilot.targets(ep,h)[mask] for h in study.HORIZONS],axis=1)
    variance=np.clip(y.mean(axis=0)*(1-y.mean(axis=0)),1e-12,None)
    candidates=[]
    for w,p in zip(weights,validation_candidates):
        normalized=float(np.mean(np.mean((p[mask]-y)**2,axis=0)/variance))
        candidates.append({'weight':float(w),'normalized_validation_brier':normalized,
            'regularized_objective':normalized+.01*w})
    chosen=min(range(len(candidates)),key=lambda i:(candidates[i]['regularized_objective'],weights[i]))
    return chosen,candidates

def predict_model(bundle,ep,available):
    """A declared empty sensor set abstains, including on zero-count input."""
    if subset_key(available)=='none':
        return {'status':'insufficient_sensors','risk':None,'stage_belief':None}
    if subset_key(available)!=bundle['available']:
        raise ValueError('Choose the expert matching the declared sensor availability')
    counts=align(ep,bundle['vocabulary']);columns=bundle['columns']
    symbols=study.symbols_for(counts,bundle['edges'])
    belief=state_filter(bundle['state_model'],symbols,columns)
    base=study.temporal_features(counts[:,columns]);aug=np.c_[base,stage_features(belief)]
    predictions={}
    for mode,features in [('available_boosting',base),('state_augmented_boosting',aug)]:
        raw=np.stack([m.predict_proba(features)[:,1] for m in bundle['estimators'][mode]],axis=1)
        predictions[mode]=np.maximum.accumulate(raw,axis=1)
    return {'status':'ok','risk':predictions,'stage_belief':belief}

def prepare_context(episodes,train):
    counts,names=study.aligned_counts(episodes,train)
    return {'counts':counts,'names':names,'state_cache':{},'train':tuple(train)}

def fit_predict(episodes,train,predict,available,context=None):
    if not available:raise ValueError('Cannot fit a forecasting expert with no sensors')
    context=prepare_context(episodes,train) if context is None else context
    if context['train']!=tuple(train):raise ValueError('Fitting context belongs to another split')
    counts,names=context['counts'],context['names']
    columns=present_columns(names,available)
    states,splits,state_model,edges=crossfit_states(episodes,counts,names,train,predict,available,context['state_cache'])
    base={n:study.temporal_features(counts[n][:,columns]) for n in train+predict}
    aug={n:np.c_[base[n],stage_features(states[n])] for n in train+predict}
    predictions={mode:{n:[] for n in predict} for mode in ['available_boosting','state_augmented_boosting']}
    models={};usage=[]
    for mode,features in [('available_boosting',base),('state_augmented_boosting',aug)]:
        x=np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train]);models[mode]=[]
        for h in study.HORIZONS:
            y=np.concatenate([pilot.targets(episodes[n],h)[pilot.preonset(episodes[n])] for n in train])
            fitted=estimator().fit(x,y);models[mode].append(fitted)
            for n in predict:predictions[mode][n].append(fitted.predict_proba(features[n])[:,1])
            if mode=='state_augmented_boosting':
                state_splits=sum(int(np.sum((~tree.nodes['is_leaf'].astype(bool))&
                    (tree.nodes['feature_idx']>=base[train[0]].shape[1]))) for trees in fitted._predictors for tree in trees)
                usage.append({'horizon':h,'splits_using_state_features':state_splits})
        for n in predict:predictions[mode][n]=np.maximum.accumulate(np.stack(predictions[mode][n],axis=1),axis=1)
    bundle={'vocabulary':names,'available':subset_key(available),'columns':columns,'edges':edges,
        'state_model':state_model,'estimators':models}
    metadata={'available':subset_key(available),'vocabulary':names,'state_crossfit_splits':splits,
        'state_likelihood_power':1/np.sqrt(len(columns)),'stage_feature_count':aug[train[0]].shape[1]-base[train[0]].shape[1],
        'state_feature_usage':usage,'seed':1729,'state_truth_used_at_prediction':False}
    return predictions,bundle,metadata

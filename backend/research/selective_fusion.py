"""Campaign-fitted calibration and horizon-specific selective state fusion."""
import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust

WEIGHTS=[0.,.1,.25,.5,1.]
MODES=['raw_counts','raw_selective','pooled_counts','pooled_state','pooled_fixed_blend','pooled_selective']


def mix(base,state,weights):
    weights=np.asarray(weights,dtype=float)
    if weights.shape!=(base.shape[1],) or np.any((weights<0)|(weights>1)):
        raise ValueError('One convex weight is required per horizon')
    return np.maximum.accumulate((1-weights)*base+weights*state,axis=1)


def select_weights(episodes,held,train):
    """Never accepts outer-test or validation forecasts for fitting selection."""
    chosen=[];audit=[]
    for j,h in enumerate(study.HORIZONS):
        errors=[]
        for weight in WEIGHTS:
            campaign={}
            for name in train:
                ep=episodes[name];mask=pilot.preonset(ep);y=pilot.targets(ep,h)[mask]
                base,state=held[name];p=(1-weight)*base[mask,j]+weight*state[mask,j]
                campaign[name]=float(np.mean((p-y)**2))
            errors.append({'weight':weight,'campaign_brier':campaign,'mean_brier':float(np.mean(list(campaign.values())))})
        scale=max(errors[0]['mean_brier'],1e-12)
        for row in errors:row['regularized_objective']=row['mean_brier']/scale+.01*row['weight']
        best=min(errors,key=lambda row:(row['regularized_objective'],row['weight']))
        chosen.append(best['weight']);audit.append({'horizon':h,'selected_weight':best['weight'],'candidates':errors})
    return chosen,audit


def fitting_arrays(episodes,predictions,train,h):
    scores=[];targets=[];weights=[]
    sizes={n:int(np.sum(pilot.preonset(episodes[n]))) for n in train};total=sum(sizes.values())
    for n in train:
        mask=pilot.preonset(episodes[n]);scores.append(predictions[n][mask])
        targets.append(pilot.targets(episodes[n],h)[mask])
        weights.append(np.full(sizes[n],total/(len(train)*sizes[n])))
    return np.concatenate(scores),np.concatenate(targets),np.concatenate(weights)


def fit_calibration(episodes,predictions,train):
    parameters=[]
    for j,h in enumerate(study.HORIZONS):
        scores,y,weight=fitting_arrays(episodes,{n:predictions[n][:,j] for n in train},train,h)
        scores=np.clip(scores,1e-8,1-1e-8);x=np.log(scores/(1-scores)).reshape(-1,1)
        fitted=LogisticRegression(C=1.,max_iter=1000).fit(x,y,sample_weight=weight)
        slope=float(fitted.coef_[0,0]);intercept=float(fitted.intercept_[0])
        prior=float(np.average(y,weights=weight))
        parameters.append({'horizon':h,'slope':max(0.,slope),'intercept':intercept,
            'constant_prior':prior if slope<0 else None,'rejected_negative_slope':slope<0,
            'fitting_campaigns':list(train),'preoutcome_bins':len(y),'equal_campaign_weights':True})
    return parameters


def calibrate(predictions,parameters):
    p=np.clip(predictions,1e-8,1-1e-8);x=np.log(p/(1-p));out=np.empty_like(p)
    for j,parameter in enumerate(parameters):
        out[:,j]=parameter['constant_prior'] if parameter['constant_prior'] is not None else expit(
            parameter['slope']*x[:,j]+parameter['intercept'])
    return np.maximum.accumulate(out,axis=1)


def predict_pair(base,state,weights,calibrators):
    raw=mix(base,state,weights);fixed=mix(base,state,np.full(base.shape[1],.25))
    inputs={'pooled_counts':base,'pooled_state':state,'pooled_fixed_blend':fixed,'pooled_selective':raw}
    return {'raw_counts':base.copy(),'raw_selective':raw,
        **{mode:calibrate(values,calibrators[mode]) for mode,values in inputs.items()}}


def predict_selective(bundle,episode,available,weights,calibrators,damage=20.,effect=.8,disruption=1.,
        forecast_mode='pooled_selective'):
    """Causal forecast plus a modeled decision; no defensive action is executed."""
    if forecast_mode not in ['pooled_selective','pooled_fixed_blend']:
        raise ValueError('Unsupported current or selective forecast mode')
    result=robust.predict_model(bundle,episode,available)
    if result['status']!='ok':
        return {**result,'recommended_action':None}
    branches=result['risk']
    if forecast_mode=='pooled_fixed_blend':
        weights=[.25]*len(study.HORIZONS)
        risk=calibrate(mix(branches['available_boosting'],branches['state_augmented_boosting'],weights),
            calibrators['pooled_fixed_blend'])
    else:
        forecasts=predict_pair(branches['available_boosting'],branches['state_augmented_boosting'],weights,calibrators)
        risk=forecasts[forecast_mode]
    losses=study.decision_costs(risk,True,damage,effect,disruption)
    actions=losses.argmin(axis=1)
    return {'status':'ok','risk':risk,'state_belief':result['stage_belief'],
        'recommended_action':study.ACTIONS[int(actions[-1])][0],
        'modeled_expected_losses':losses[-1].tolist(),'weights':list(weights)}


def predict_current(bundle,episode,available,calibrators,damage=20.,effect=.8,disruption=1.):
    """Frozen research default: fixed .25 state blend and pooled calibration."""
    result=predict_selective(bundle,episode,available,[.25]*len(study.HORIZONS),calibrators,
        damage,effect,disruption,forecast_mode='pooled_fixed_blend')
    return {**result,'forecast_mode':'pooled_fixed_blend','primary_horizon_minutes':30}

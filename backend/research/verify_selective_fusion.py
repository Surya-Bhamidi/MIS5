"""Independently reconstruct fitting choices, forecasts, alarms and costs."""
import io
import json
import unittest
from datetime import datetime,timezone

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust
from run_selective_fusion import OUT,PREVIOUS,cache_paths,cache_signature
from selective_fusion import MODES,WEIGHTS
from audit_endpoints import OUT as VALIDATION
from verify_comparison import metrics,compare


def equal(a,b,tolerance=1e-12):
    assert a.shape==b.shape and float(np.max(np.abs(a-b)))<=tolerance


def transformed(p,parameters):
    p=np.clip(p,1e-8,1-1e-8);logits=np.log(p)-np.log1p(-p);columns=[]
    for j,r in enumerate(parameters):
        columns.append(np.full(len(p),r['constant_prior']) if r['constant_prior'] is not None
            else expit(logits[:,j]*r['slope']+r['intercept']))
    return np.maximum.accumulate(np.array(columns).T,axis=1)


def check_calibrator(ep,inputs,train,parameters):
    for j,h in enumerate(study.HORIZONS):
        chunks=[inputs[n][ep[n]['times']<ep[n]['onset'],j] for n in train]
        labels=[(ep[n]['onset']-ep[n]['times'][ep[n]['times']<ep[n]['onset']]<=h*60).astype(int) for n in train]
        total=sum(len(v) for v in chunks)
        weight=np.concatenate([np.full(len(v),total/(6*len(v))) for v in chunks])
        p=np.clip(np.concatenate(chunks),1e-8,1-1e-8);y=np.concatenate(labels)
        fitted=LogisticRegression(C=1,max_iter=1000).fit(np.log(p/(1-p)).reshape(-1,1),y,sample_weight=weight)
        r=parameters[j]
        assert r['fitting_campaigns']==train and r['preoutcome_bins']==total
        assert r['rejected_negative_slope']==bool(fitted.coef_[0,0]<0)
        assert abs(r['slope']-max(0,fitted.coef_[0,0]))<1e-12
        assert abs(r['intercept']-fitted.intercept_[0])<1e-12
        if fitted.coef_[0,0]<0:assert abs(r['constant_prior']-np.average(y,weights=weight))<1e-12
        else:assert r['constant_prior'] is None


def run():
    pilot.HORIZONS=study.HORIZONS
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(pilot.ROOT/'backend/tests'))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    assert result.wasSuccessful(),stream.getvalue()
    episodes=study.load('ait');signature=cache_signature()
    inner=list((OUT/'inner_predictions').glob('*.json'));assert len(inner)==280
    vocabularies={}
    for path in inner:
        m=json.loads(path.read_text());train=m['train'];assert len(train)==5
        assert m['cache_signature']==signature
        assert set(m['predicted_campaigns'])==set(pilot.SCENARIOS)-set(train)
        assert len(m['state_crossfit_splits'])==5 and max(m['prefix_errors'].values())<1e-10
        for split in m['state_crossfit_splits']:
            assert set(split['fitting_campaigns'])==set(train)-{split['prediction_campaign']}
            assert len(split['fitting_campaigns'])==4 and not set(m['predicted_campaigns'])&set(split['fitting_campaigns'])
        identity=tuple(train)
        if identity not in vocabularies:vocabularies[identity]=study.aligned_counts(episodes,train)[1]
        assert m['vocabulary']==vocabularies[identity]
        with np.load(path.with_suffix('.npz')) as saved:
            assert len(saved.files)==6
            for name in m['predicted_campaigns']:
                for mode in ['available_boosting','state_augmented_boosting']:
                    p=saved[name+'__'+mode]
                    assert p.shape==(len(episodes[name]['times']),6)
                    assert np.isfinite(p).all() and np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
    metadata=json.loads((OUT/'metadata.json').read_text());assert len(metadata)==56
    predictions={};meta_lookup={}
    for m in metadata:
        test=m['test'];val=m['validation'];train=m['train'];key=(test,m['available']);meta_lookup[key]=m
        assert len(train)==6 and not set(train)&{test,val}
        assert val==pilot.SCENARIOS[(pilot.SCENARIOS.index(test)+1)%8]
        assert not m['selection_uses_test'] and not m['calibration_uses_outer_validation']
        held={}
        for n in train:
            path,meta=cache_paths(set(train)-{n},m['available'].split('+'))
            record=json.loads(meta.read_text());assert n not in record['train'] and test not in record['train'] and val not in record['train']
            with np.load(path) as saved:held[n]=(saved[n+'__available_boosting'].copy(),saved[n+'__state_augmented_boosting'].copy())
        selected=[]
        for j,h in enumerate(study.HORIZONS):
            candidates=[]
            for w in WEIGHTS:
                errors={}
                for n in train:
                    ep=episodes[n];mask=ep['times']<ep['onset'];y=(ep['onset']-ep['times'][mask]<=h*60).astype(int)
                    p=(1-w)*held[n][0][mask,j]+w*held[n][1][mask,j]
                    errors[n]=float(np.mean((p-y)**2))
                candidates.append((w,float(np.mean(list(errors.values()))),errors))
            scale=max(candidates[0][1],1e-12)
            best=min(candidates,key=lambda c:(c[1]/scale+.01*c[0],c[0]));selected.append(best[0])
            audit=m['selection'][j]
            for actual,expected in zip(audit['candidates'],candidates):
                assert actual['weight']==expected[0] and abs(actual['mean_brier']-expected[1])<1e-12
                assert abs(actual['regularized_objective']-(expected[1]/scale+.01*expected[0]))<1e-12
                for n in train:assert abs(actual['campaign_brier'][n]-expected[2][n])<1e-12
            assert audit['selected_weight']==best[0]
        assert selected==m['weights'];w=np.array(selected)
        fitting={'pooled_counts':{n:held[n][0] for n in train},'pooled_state':{n:held[n][1] for n in train},
            'pooled_fixed_blend':{n:np.maximum.accumulate(.75*held[n][0]+.25*held[n][1],axis=1) for n in train},
            'pooled_selective':{n:np.maximum.accumulate((1-w)*held[n][0]+w*held[n][1],axis=1) for n in train}}
        for mode,values in fitting.items():check_calibrator(episodes,values,train,m['calibrators'][mode])
        outer={}
        for label,mode in [('base','available_boosting'),('state','state_augmented_boosting')]:
            with np.load(PREVIOUS/'predictions'/f'ait_{test}_{m["available"]}_{mode}.npz') as saved:
                outer[label]={k:saved[k].copy() for k in ['raw','validation_raw']}
        for mode in MODES:
            with np.load(OUT/'predictions'/f'ait_{test}_{m["available"]}_{mode}.npz') as saved:
                predictions[(*key,mode)]={k:saved[k].copy() for k in ['risk','validation_risk']}
            for label,source in [('risk','raw'),('validation_risk','validation_raw')]:
                base=outer['base'][source];state=outer['state'][source]
                raw=np.maximum.accumulate((1-w)*base+w*state,axis=1)
                inputs={'pooled_counts':base,'pooled_state':state,'pooled_fixed_blend':np.maximum.accumulate(.75*base+.25*state,axis=1),
                    'pooled_selective':raw}
                expected=base if mode=='raw_counts' else raw if mode=='raw_selective' else transformed(inputs[mode],m['calibrators'][mode])
                p=predictions[(*key,mode)][label];equal(p,expected)
                assert np.isfinite(p).all() and np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
                if mode=='raw_counts':np.testing.assert_array_equal(p,base)
        for j,h in enumerate(study.HORIZONS):
            contribution=m['state_contribution'][str(h)]
            assert contribution['selected_weight']==w[j]
            for tag,a,b in [('raw','raw_selective','raw_counts'),('calibrated','pooled_selective','pooled_counts')]:
                changed=int(np.sum(np.abs(predictions[(*key,a)]['risk'][:,j]-predictions[(*key,b)]['risk'][:,j])>1e-12))
                assert contribution[tag+'_changed_minutes']==changed
    thresholds=json.loads((OUT/'thresholds.json').read_text());assert len(thresholds)==8064
    lookup={}
    for r in thresholds:
        key=(r['test'],r['available'],r['mode']);j=study.HORIZONS.index(r['horizon'])
        rec=metrics(episodes[r['validation']],predictions[key]['validation_risk'][:,j],r['horizon'],r['threshold'])
        compare(r['validation_metrics'],rec)
        assert rec['false_warnings_per_24h']<=r['budget']+1e-12 and rec['negative_warning_minutes']<=5
        lookup[(*key,r['horizon'],r['budget'])]=r['threshold']
    roots={r['scenario']:r['successful_root'] for r in json.loads((VALIDATION/'endpoint_evidence.json').read_text())}
    rows=json.loads((OUT/'scored.json').read_text());assert len(rows)==23040
    for r in rows:
        key=(r['scenario'],r['available'],r['mode']);ep=episodes[r['scenario']]
        if r['endpoint']=='successful_root':ep={**ep,'onset':roots[r['scenario']]}
        p=predictions[key]['risk'][:,study.HORIZONS.index(r['horizon'])];d=r['delay_minutes']
        if d:p=np.r_[np.zeros(d),p[:-d]]
        assert r['threshold']==lookup[(*key,r['horizon'],r['budget'])]
        compare(r,metrics(ep,p,r['horizon'],r['threshold']))
    decisions=json.loads((OUT/'decisions.json').read_text());assert len(decisions)==9072
    for r in decisions:
        ep=episodes[r['scenario']];mask=ep['times']<ep['onset']
        risk=predictions[(r['scenario'],r['available'],r['mode'])]['risk'][mask]
        remaining=(ep['onset']-ep['times'][mask])/60;imminent=(remaining<=30).astype(float)
        for label,aware in [('delay_aware',True),('ignores_delay',False)]:
            expected=[]
            for _,delay,effect,price in study.ACTIONS:
                p30=risk[:,study.HORIZONS.index(30)]
                late=risk[:,study.HORIZONS.index(delay)] if aware and delay else np.zeros(len(risk))
                expected.append(price*r['disruption_scale']+r['damage']*(p30-min(1,effect*r['effect_scale'])*np.maximum(0,p30-late)))
            actions=np.array(expected).T.argmin(axis=1)
            delay=np.array([a[1] for a in study.ACTIONS])[actions]
            effect=np.minimum(1,np.array([a[2] for a in study.ACTIONS])*r['effect_scale'])[actions]
            price=np.array([a[3] for a in study.ACTIONS])[actions]*r['disruption_scale']
            realized=price+r['damage']*(imminent-effect*imminent*(remaining>delay))
            assert abs(realized.mean()-r[label]['mean_assumed_cost'])<1e-12
            assert r[label]['actions']=={a[0]:int(np.sum(actions==i)) for i,a in enumerate(study.ACTIONS)}
        assert abs(r['improvement']-(r['ignores_delay']['mean_assumed_cost']-r['delay_aware']['mean_assumed_cost']))<1e-12
    transfer=json.loads((OUT/'cam_transfer.json').read_text());assert len(transfer)==432
    for r in transfer:
        with np.load(OUT/'predictions'/f'cam_{r["scenario"]}_{r["mode"]}.npz') as saved:
            ep={'times':saved['times'],'onset':float(saved['onset'])};p=saved['risk'][:,study.HORIZONS.index(r['horizon'])]
        rec=metrics(ep,p,r['horizon'],r['threshold'])
        if not np.any(ep['times']<ep['onset']-r['horizon']*60):
            assert r['false_warnings_per_24h'] is None;rec.pop('false_warnings_per_24h')
        compare(r,rec);assert r['threshold']==lookup[('fox','suricata+wazuh',r['mode'],r['horizon'],r['budget'])]
    record={'passed':True,'regression_tests':result.testsRun,'regression_output':stream.getvalue(),
        'unique_five_campaign_fits':len(vocabularies),'inner_availability_fits':len(inner),
        'outer_availability_settings':len(metadata),'forecast_variants':len(MODES),'validation_thresholds':len(thresholds),
        'endpoint_budget_delay_rows':len(rows),'assumed_decision_settings':len(decisions),'external_proxy_rows':len(transfer),
        'checks':['five-campaign fitting exclusion','four-campaign HMM training features','causal fitted prefixes',
            'independent weight reconstruction','independent equal-campaign calibrator refits','forecast reconstruction and raw reference equality',
            'independent alarm metrics and frozen validation budgets','state contribution accounting','independent assumed utility arithmetic'],
        'utc':datetime.now(timezone.utc).isoformat(),'status':'exploratory; already inspected campaigns; assumed response efficacy'}
    (OUT/'verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='regression_output'},indent=2),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=2):run()

"""Independent checks of revised forecast records, splits and Decision Network."""
import hashlib
import json
import unittest
import io
from datetime import datetime,timezone

import numpy as np

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust
from run_robust_forecasting import OUT,MODES,WEIGHTS
from audit_endpoints import OUT as VALIDATION
from verify_comparison import metrics,compare

def run():
    suite=unittest.defaultTestLoader.discover(str(pilot.ROOT/'backend/tests'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    assert result.wasSuccessful(),stream.getvalue()
    episodes=study.load('ait');metadata=json.loads((OUT/'metadata.json').read_text())
    folds=json.loads((OUT/'fold_results.json').read_text());assert len(metadata)==56 and len(folds)==168
    predictions={};references={};selection={}
    for m in metadata:
        assert len(m['train'])==6 and not set(m['train'])&{m['test'],m['validation']}
        assert m['validation']==pilot.SCENARIOS[(pilot.SCENARIOS.index(m['test'])+1)%8]
        assert len(m['state_crossfit_splits'])==6
        for split in m['state_crossfit_splits']:
            assert len(split['fitting_campaigns'])==5
            assert split['prediction_campaign'] not in split['fitting_campaigns']
            assert set(split['fitting_campaigns'])==set(m['train'])-{split['prediction_campaign']}
        assert max(m['prefix_max_errors'].values())<1e-10
        assert m['no_sensor_status']=='insufficient_sensors'
        candidates=m['blend']['candidates'];assert [c['weight'] for c in candidates]==WEIGHTS
        selected=min(candidates,key=lambda c:(c['regularized_objective'],c['weight']))
        assert selected['weight']==m['blend']['selected_weight']
        for c in candidates:assert abs(c['regularized_objective']-c['normalized_validation_brier']-.01*c['weight'])<1e-12
        assert not m['blend']['selection_uses_test']
        selection[(m['test'],m['available'])]=m['blend']['selected_weight']
    for fold in folds:
        key=(fold['test'],fold['available'],fold['mode']);references[key]=fold
        with np.load(OUT/'predictions'/f'ait_{key[0]}_{key[1]}_{key[2]}.npz') as saved:
            predictions[key]={k:saved[k].copy() for k in ['raw','calibrated','validation_raw','validation_calibrated']}
        for k,p in predictions[key].items():
            assert np.isfinite(p).all() and np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
            name=fold['validation'] if k.startswith('validation') else fold['test']
            assert len(p)==len(episodes[name]['times'])
        for label in ['raw','calibrated']:
            for j,h in enumerate(study.HORIZONS):
                r=fold[label][str(h)]
                compare(r,metrics(episodes[fold['test']],predictions[key][label][:,j],h,r['threshold']))
    # Reconstruct selected raw mixtures independently from archived base/augmented.
    for test,available in selection:
        a=predictions[(test,available,MODES[0])];b=predictions[(test,available,MODES[1])]
        selected=predictions[(test,available,MODES[2])];w=selection[(test,available)]
        for label in ['raw','validation_raw']:
            np.testing.assert_allclose(selected[label],(1-w)*a[label]+w*b[label],atol=1e-15)
        ep=episodes[references[(test,available,MODES[2])]['validation']];mask=ep['times']<ep['onset']
        y=np.stack([(ep['onset']-ep['times'][mask]<=h*60).astype(int) for h in study.HORIZONS],axis=1)
        variance=np.clip(y.mean(axis=0)*(1-y.mean(axis=0)),1e-12,None)
        normalized=float(np.mean(np.mean((selected['validation_calibrated'][mask]-y)**2,axis=0)/variance))
        meta=next(m for m in metadata if (m['test'],m['available'])==(test,available))
        candidate=next(c for c in meta['blend']['candidates'] if c['weight']==w)
        assert abs(normalized-candidate['normalized_validation_brier'])<1e-12
    thresholds=json.loads((OUT/'thresholds.json').read_text());assert len(thresholds)==4032
    lookup={}
    for r in thresholds:
        key=(r['test'],r['available'],r['mode']);j=study.HORIZONS.index(r['horizon'])
        ep=episodes[r['validation']];score=metrics(ep,predictions[key]['validation_calibrated'][:,j],r['horizon'],r['threshold'])
        compare(r['validation_metrics'],score)
        assert score['false_warnings_per_24h']<=r['budget']+1e-12 and score['negative_warning_minutes']<=5
        lookup[(r['test'],r['available'],r['mode'],r['horizon'],r['budget'])]=r['threshold']
    roots={r['scenario']:r['successful_root'] for r in json.loads((VALIDATION/'endpoint_evidence.json').read_text())}
    rows=json.loads((OUT/'scored.json').read_text());assert len(rows)==11520
    for r in rows:
        ep=episodes[r['scenario']]
        if r['endpoint']=='successful_root':ep={**ep,'onset':roots[r['scenario']]}
        key=(r['scenario'],r['available'],r['mode']);j=study.HORIZONS.index(r['horizon'])
        p=predictions[key]['calibrated'][:,j].copy();delay=r['delay_minutes']
        if delay:p=np.r_[np.zeros(delay),p[:-delay]]
        threshold=lookup[(*key,r['horizon'],r['budget'])]
        assert threshold==r['threshold'];compare(r,metrics(ep,p,r['horizon'],threshold))
    decisions=json.loads((OUT/'decisions.json').read_text());assert len(decisions)==4536
    assert {r['effect_scale'] for r in decisions}=={.5,.8,1.}
    for r in decisions:
        ep=episodes[r['scenario']];p=predictions[(r['scenario'],r['available'],r['mode'])]['calibrated']
        mask=ep['times']<ep['onset'];p=p[mask];remaining=(ep['onset']-ep['times'][mask])/60
        for label,include_delay in [('delay_aware',True),('ignores_delay',False)]:
            expected=[]
            for _,delay,effect,disruption in study.ACTIONS:
                chance=p[:,study.HORIZONS.index(30)]
                soon=p[:,study.HORIZONS.index(delay)] if include_delay and delay else np.zeros(len(p))
                expected.append(disruption*r['disruption_scale']+r['damage']*(chance-min(1,effect*r['effect_scale'])*np.maximum(0,chance-soon)))
            actions=np.array(expected).T.argmin(axis=1)
            action_delays=np.array([a[1] for a in study.ACTIONS])[actions]
            action_effects=np.minimum(1,np.array([a[2] for a in study.ACTIONS])*r['effect_scale'])[actions]
            prices=np.array([a[3] for a in study.ACTIONS])[actions]*r['disruption_scale']
            imminent=(remaining<=30).astype(float)
            realized=prices+r['damage']*(imminent-action_effects*imminent*(remaining>action_delays))
            assert abs(np.mean(realized)-r[label]['mean_assumed_cost'])<1e-12
        assert abs(r['improvement']-(r['ignores_delay']['mean_assumed_cost']-r['delay_aware']['mean_assumed_cost']))<1e-12
    transfer=json.loads((OUT/'cam_transfer.json').read_text());assert len(transfer)==216
    for r in transfer:
        with np.load(OUT/'predictions'/f'cam_{r["scenario"]}_{r["mode"]}.npz') as saved:
            p=saved['calibrated'][:,study.HORIZONS.index(r['horizon'])]
            ep={'times':saved['times'],'onset':float(saved['onset'])}
        rec=metrics(ep,p,r['horizon'],r['threshold'])
        if not np.any(ep['times']<ep['onset']-r['horizon']*60):
            assert r['false_warnings_per_24h'] is None;rec.pop('false_warnings_per_24h')
        compare(r,rec)
        assert r['threshold']==lookup[('fox','suricata+wazuh',r['mode'],r['horizon'],r['budget'])]
    reproduction=json.loads((OUT/'baseline_reproduction.json').read_text())
    assert len(reproduction)==32 and max(r['max_error'] for r in reproduction)<1e-10
    context_folds=json.loads((OUT/'context_folds.json').read_text());assert len(context_folds)==16
    context_predictions={}
    for r in context_folds:
        assert len(r['train'])==6 and not set(r['train'])&{r['test'],r['validation']}
        key=(r['test'],r['mode'])
        with np.load(OUT/'predictions'/f'ait_{key[0]}_{key[1]}.npz') as saved:
            context_predictions[key]={k:saved[k].copy() for k in ['raw','calibrated','validation_raw','validation_calibrated']}
        for label in ['raw','calibrated']:
            for j,h in enumerate(study.HORIZONS):
                s=r[label][str(h)];compare(s,metrics(episodes[r['test']],context_predictions[key][label][:,j],h,s['threshold']))
    context_thresholds=json.loads((OUT/'context_thresholds.json').read_text());assert len(context_thresholds)==384
    context_lookup={}
    for r in context_thresholds:
        key=(r['test'],r['mode']);j=study.HORIZONS.index(r['horizon'])
        rec=metrics(episodes[r['validation']],context_predictions[key]['validation_calibrated'][:,j],r['horizon'],r['threshold'])
        compare(r['validation_metrics'],rec)
        assert rec['false_warnings_per_24h']<=r['budget']+1e-12 and rec['negative_warning_minutes']<=5
        context_lookup[(*key,r['horizon'],r['budget'])]=r['threshold']
    context_rows=json.loads((OUT/'context_scored.json').read_text());assert len(context_rows)==768
    for r in context_rows:
        ep=episodes[r['scenario']]
        if r['endpoint']=='successful_root':ep={**ep,'onset':roots[r['scenario']]}
        key=(r['scenario'],r['mode']);j=study.HORIZONS.index(r['horizon'])
        assert r['threshold']==context_lookup[(*key,r['horizon'],r['budget'])]
        compare(r,metrics(ep,context_predictions[key]['calibrated'][:,j],r['horizon'],r['threshold']))
    gates=json.loads((OUT/'gate_selection.json').read_text());assert len(gates)==1344
    gate_predictions={};gate_lookup={}
    for test in pilot.SCENARIOS:
        for available in robust.SUBSETS:
            key=(test,robust.subset_key(available))
            with np.load(OUT/'predictions'/f'gated_ait_{key[0]}_{key[1]}.npz') as saved:
                gate_predictions[key]={k:saved[k].copy() for k in ['calibrated','validation_calibrated','state_belief','validation_state_belief']}
            for label in ['calibrated','validation_calibrated']:
                np.testing.assert_array_equal(gate_predictions[key][label],predictions[(*key,MODES[0])][label])
    def effective(p,belief,level):
        q=belief[:,max(1,belief.shape[1]-2):].sum(axis=1)
        return np.where(q>=level,p,-1.)
    def checked_gate_metrics(ep,p,belief,h,choice):
        rec=metrics(ep,effective(p,belief,choice['level']),h,choice['threshold'])
        proper=metrics(ep,p,h,choice['threshold'])
        rec['brier']=proper['brier'];rec['average_precision']=proper['average_precision']
        return rec
    for r in gates:
        key=(r['test'],r['available']);gp=gate_predictions[key];j=study.HORIZONS.index(r['horizon']);ep=episodes[r['validation']]
        assert not r['selection_uses_test'] and len(r['candidates'])==3
        for c in r['candidates']:
            rec=checked_gate_metrics(ep,gp['validation_calibrated'][:,j],gp['validation_state_belief'],r['horizon'],c)
            compare(c['validation_warning_metrics'],{k:rec[k] for k in c['validation_warning_metrics']})
            assert rec['false_warnings_per_24h']<=r['budget']+1e-12 and rec['negative_warning_minutes']<=5
        def rank(c):
            s=c['validation_warning_metrics'];return (s['strict_warning_recall'],s['strict_lead_minutes'] or 0,
                -s['negative_warning_minutes'],-s['false_warning_episodes'],-c['level'])
        assert max(r['candidates'],key=rank)==r['chosen']
        gate_lookup[(*key,r['horizon'],r['budget'])]=r['chosen']
    gate_rows=json.loads((OUT/'gate_scored.json').read_text());assert len(gate_rows)==2688
    for r in gate_rows:
        key=(r['scenario'],r['available']);gp=gate_predictions[key];ep=episodes[r['scenario']]
        if r['endpoint']=='successful_root':ep={**ep,'onset':roots[r['scenario']]}
        j=study.HORIZONS.index(r['horizon']);choice=gate_lookup[(*key,r['horizon'],r['budget'])]
        compare(r,checked_gate_metrics(ep,gp['calibrated'][:,j],gp['state_belief'],r['horizon'],choice))
    gate_decisions=json.loads((OUT/'gate_decisions.json').read_text());assert len(gate_decisions)==1512
    for r in gate_decisions:
        key=(r['scenario'],r['available']);gp=gate_predictions[key];ep=episodes[r['scenario']]
        mask=ep['times']<ep['onset'];risk=gp['calibrated'][mask];remaining=(ep['onset']-ep['times'][mask])/60
        choice=gate_lookup[(*key,30,1)]
        active=effective(gp['calibrated'][:,study.HORIZONS.index(30)],gp['state_belief'],choice['level'])[mask]>=choice['threshold']
        for label,aware in [('delay_aware',True),('ignores_delay',False)]:
            expected=[]
            for _,delay,effect,disruption in study.ACTIONS:
                p30=risk[:,study.HORIZONS.index(30)]
                late=risk[:,study.HORIZONS.index(delay)] if aware and delay else np.zeros(len(risk))
                expected.append(disruption*r['disruption_scale']+r['damage']*(p30-min(1,effect*r['effect_scale'])*np.maximum(0,p30-late)))
            actions=np.array(expected).T.argmin(axis=1);actions[~active]=0
            delay=np.array([a[1] for a in study.ACTIONS])[actions]
            effect=np.minimum(1,np.array([a[2] for a in study.ACTIONS])*r['effect_scale'])[actions]
            price=np.array([a[3] for a in study.ACTIONS])[actions]*r['disruption_scale']
            imminent=(remaining<=30).astype(float)
            loss=price+r['damage']*(imminent-effect*imminent*(remaining>delay))
            assert abs(np.mean(loss)-r[label]['mean_assumed_cost'])<1e-12
    gate_cam=json.loads((OUT/'gate_cam.json').read_text());assert len(gate_cam)==72
    for r in gate_cam:
        with np.load(OUT/'predictions'/f'gated_cam_{r["scenario"]}.npz') as saved:
            belief=saved['state_belief'];ep={'times':saved['times'],'onset':float(saved['onset'])}
        with np.load(OUT/'predictions'/f'cam_{r["scenario"]}_available_boosting.npz') as saved:
            p=saved['calibrated'][:,study.HORIZONS.index(r['horizon'])]
        choice=gate_lookup[('fox','suricata+wazuh',r['horizon'],r['budget'])]
        rec=checked_gate_metrics(ep,p,belief,r['horizon'],choice)
        if not np.any(ep['times']<ep['onset']-r['horizon']*60):
            assert r['false_warnings_per_24h'] is None;rec.pop('false_warnings_per_24h')
        compare(r,rec)
    record={'passed':True,'regression_tests':result.testsRun,'regression_output':stream.getvalue(),
        'fitting_availability_settings':56,'forecast_folds':168,'baseline_reproductions':32,
        'validation_thresholds':4032,'endpoint_budget_delay_rows':11520,'decision_settings':4536,
        'external_diagnostic_rows':216,'context_control_folds':16,'context_test_rows':768,
        'gate_test_rows':2688,'gate_policy_settings':1512,'gate_external_rows':72,
        'checks':['causal prefixes','no test truth in features','leave-campaign-out HMM stage features',
            'explicit availability and abstention','all saved scores independently recomputed','frozen validation thresholds',
            'selected mixture reconstructed','independent expected and realized assumed utility arithmetic',
            'clock and longer-history controls','state gating preserves probability forecasts','validation-only confirmation selection'],
        'utc':datetime.now(timezone.utc).isoformat(),'status':'exploratory; costs/effects assumed; no new independent campaigns'}
    (OUT/'verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='regression_output'},indent=2),flush=True)

if __name__=='__main__':run()

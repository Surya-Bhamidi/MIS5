"""Use BN/HMM evidence for alarms while preserving the count risk forecast."""
import json
import time

import numpy as np
from threadpoolctl import threadpool_limits

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust
from run_robust_forecasting import OUT,score
from audit_endpoints import OUT as VALIDATION
from comparison_audit import select_threshold,BUDGETS
from cam_transfer import prepare as prepare_cam

GATES=[0,.5,.9]

def alarm_score(p,belief,level):
    # Alarm eligibility is distinct from probability. Do not score this as risk.
    mass=belief[:,max(1,belief.shape[1]-2):].sum(axis=1)
    return np.where(mass>=level,p,-1.)

def choose_gate(ep,p,belief,h,budget):
    candidates=[]
    for level in GATES:
        alarm=alarm_score(p,belief,level)
        threshold=select_threshold(ep,alarm,h,budget)
        assert threshold>=0
        r=score(ep,alarm,h,threshold)
        candidates.append({'level':level,'threshold':threshold,'validation_warning_metrics':{
            k:r[k] for k in ['strict_warning_recall','strict_lead_minutes','false_warning_episodes',
                'negative_warning_minutes','false_warnings_per_24h']}})
    def rank(c):
        r=c['validation_warning_metrics']
        return (r['strict_warning_recall'],r['strict_lead_minutes'] or 0,-r['negative_warning_minutes'],
            -r['false_warning_episodes'],-c['level'])
    chosen=max(candidates,key=rank)
    return chosen,candidates

def gated_metrics(ep,p,belief,h,selection):
    alarm=alarm_score(p,belief,selection['level'])
    result=score(ep,alarm,h,selection['threshold'])
    # Evaluate probability error/ranking on the preserved count forecast only.
    proper=score(ep,p,h,selection['threshold'])
    result['brier']=proper['brier'];result['average_precision']=proper['average_precision']
    result['confirmation_level']=selection['level']
    plain=p>=selection['threshold'];gated=alarm>=selection['threshold']
    result['suppressed_warning_minutes']=int(np.sum((plain&~gated)&pilot.preonset(ep)))
    return result

def gated_policy_cost(ep,p,belief,selection,aware,damage,effect,disruption):
    mask=pilot.preonset(ep);risk=p[mask];remaining=(ep['onset']-ep['times'][mask])/60
    active=alarm_score(p[:,study.HORIZONS.index(30)],belief,selection['level'])[mask]>=selection['threshold']
    actions=study.decision_costs(risk,aware,damage,effect,disruption).argmin(axis=1)
    actions[~active]=0
    delays=np.array([a[1] for a in study.ACTIONS])[actions]
    effects=np.minimum(1,np.array([a[2] for a in study.ACTIONS])*effect)[actions]
    prices=np.array([a[3] for a in study.ACTIONS])[actions]*disruption
    imminent=(remaining<=30).astype(float)
    realized=prices+damage*(imminent-effects*imminent*(remaining>delays))
    return {'mean_assumed_cost':float(realized.mean()),
        'actions':{a[0]:int(np.sum(actions==i)) for i,a in enumerate(study.ACTIONS)}}

def run():
    pilot.HORIZONS=study.HORIZONS;episodes=study.load('ait');cam,_=prepare_cam();episodes.update(cam)
    roots={r['scenario']:r['successful_root'] for r in json.loads((VALIDATION/'endpoint_evidence.json').read_text())}
    selections=[];scored=[];transfers=[];decisions=[];metadata=[]
    for fold,test in enumerate(pilot.SCENARIOS):
        start=time.monotonic();val=pilot.SCENARIOS[(fold+1)%8]
        train=[n for n in pilot.SCENARIOS if n not in [val,test]]
        context=robust.prepare_context(episodes,train)
        model,edges=robust.fit_state(episodes,context['counts'],train)
        for available in robust.SUBSETS:
            key=robust.subset_key(available);columns=robust.present_columns(context['names'],available)
            extras=list(cam) if test=='fox' and available==('suricata','wazuh') else []
            beliefs={n:robust.state_filter(model,study.symbols_for(context['counts'][n],edges),columns) for n in [val,test]+extras}
            with np.load(OUT/'predictions'/f'ait_{test}_{key}_available_boosting.npz') as saved:
                vp=saved['validation_calibrated'].copy();p=saved['calibrated'].copy()
            np.savez_compressed(OUT/'predictions'/f'gated_ait_{test}_{key}.npz',calibrated=p,
                validation_calibrated=vp,state_belief=beliefs[test],validation_state_belief=beliefs[val],
                times=episodes[test]['times'],onset=episodes[test]['onset'],horizons=study.HORIZONS)
            local={}
            for j,h in enumerate(study.HORIZONS):
                for budget in BUDGETS:
                    chosen,candidates=choose_gate(episodes[val],vp[:,j],beliefs[val],h,budget)
                    local[(h,budget)]=chosen
                    selections.append({'test':test,'validation':val,'train':train,'available':key,'horizon':h,'budget':budget,
                        'chosen':chosen,'candidates':candidates,'selection_uses_test':False})
                    for endpoint,onset in [('scheduled_onset',episodes[test]['onset']),('successful_root',roots[test])]:
                        ep={**episodes[test],'onset':onset}
                        scored.append({'scenario':test,'mode':'state_confirmed_alarm','available':key,'horizon':h,
                            'budget':budget,'endpoint':endpoint,'delay_minutes':0,**gated_metrics(ep,p[:,j],beliefs[test],h,chosen)})
                    for n in extras:
                        with np.load(OUT/'predictions'/f'cam_{n}_available_boosting.npz') as saved:cp=saved['calibrated']
                        transfers.append({'scenario':n,'mode':'state_confirmed_alarm','available':key,'horizon':h,'budget':budget,
                            'endpoint':'executed_privilege_tactic_proxy',**gated_metrics(episodes[n],cp[:,j],beliefs[n],h,chosen)})
            for damage in [10.,20.,50.]:
                for effect in [.5,.8,1.]:
                    for disruption in [.5,1.,2.]:
                        choice=local[(30,1)]
                        aware=gated_policy_cost(episodes[test],p,beliefs[test],choice,True,damage,effect,disruption)
                        blind=gated_policy_cost(episodes[test],p,beliefs[test],choice,False,damage,effect,disruption)
                        decisions.append({'scenario':test,'available':key,'damage':damage,'effect_scale':effect,
                            'disruption_scale':disruption,'delay_aware':aware,'ignores_delay':blind,
                            'improvement':blind['mean_assumed_cost']-aware['mean_assumed_cost'],
                            'status':'separate alarm-conditioned assumed policy; no real interventions'})
            metadata.append({'test':test,'validation':val,'train':train,'available':key,
                'prefix_max_error':float(np.max(np.abs(beliefs[test][:17]-robust.state_filter(model,
                    study.symbols_for(context['counts'][test][:17],edges),columns)))),
                'probability_change':0.0})
            for n in extras:
                np.savez_compressed(OUT/'predictions'/f'gated_cam_{n}.npz',state_belief=beliefs[n],
                    times=episodes[n]['times'],onset=episodes[n]['onset'])
        for name,values in [('gate_selection.json',selections),('gate_scored.json',scored),('gate_cam.json',transfers),
            ('gate_decisions.json',decisions),('gate_metadata.json',metadata)]:
            (OUT/name).write_text(json.dumps(values,indent=2),encoding='utf-8')
        print(f'Separated alarm {fold+1}/8 {test}: {time.monotonic()-start:.1f}s',flush=True)
    print('Saved probability-preserving alarm revision:',len(scored),'test rows',flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=2):run()

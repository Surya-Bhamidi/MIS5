"""Run fixed revised variants and their paired availability/delay diagnostics."""
import argparse
import json
import time

import numpy as np
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust
from audit_endpoints import OUT as VALIDATION,strict_warning_metrics,delayed
from comparison_audit import select_threshold,BUDGETS
from cam_transfer import prepare as prepare_cam

OUT=pilot.ROOT/'experiments/robust_forecasting'
MODES=['available_boosting','state_augmented_boosting','validated_state_fusion']
WEIGHTS=[0,.25,.5,.75,1]

def save_json(name,rows):
    (OUT/name).write_text(json.dumps(rows,indent=2),encoding='utf-8')

def score(ep,p,h,threshold):
    result=strict_warning_metrics(ep,p,h,threshold)
    mask=pilot.preonset(ep);y=pilot.targets(ep,h)[mask]
    exposure=float(np.sum(y==0)/60)
    result.update(brier=float(np.mean((p[mask]-y)**2)),
        average_precision=float(average_precision_score(y,p[mask])),
        negative_exposure_hours=exposure,
        false_warnings_per_24h=None if exposure==0 else result['false_warning_episodes']/exposure*24)
    return result

def revised_pairs(ep,predicted,val,test,extras):
    calibrated={};calibration_candidates=[];test_candidates=[];extra_candidates=[]
    for mode in MODES[:2]:
        _,tp=pilot.calibrate(ep,predicted[mode][val],predicted[mode][test])
        vp,_=pilot.calibrate(ep,predicted[mode][val],predicted[mode][test])
        calibrated[mode]={'validation':vp,'test':tp,'raw_validation':predicted[mode][val],
            'raw_test':predicted[mode][test],'extras':{}}
        for n in extras:
            _,p=pilot.calibrate(ep,predicted[mode][val],predicted[mode][n]);calibrated[mode]['extras'][n]=p
    for weight in WEIGHTS:
        vp=robust.blend_predictions(predicted[MODES[0]][val],predicted[MODES[1]][val],weight)
        tp=robust.blend_predictions(predicted[MODES[0]][test],predicted[MODES[1]][test],weight)
        cvp,cp=pilot.calibrate(ep,vp,tp)
        calibration_candidates.append(cvp);test_candidates.append(cp)
        extra_candidates.append({n:pilot.calibrate(ep,vp,robust.blend_predictions(predicted[MODES[0]][n],predicted[MODES[1]][n],weight))[1] for n in extras})
    chosen,candidates=robust.select_blend(ep,calibration_candidates,WEIGHTS)
    w=WEIGHTS[chosen]
    calibrated[MODES[2]]={'validation':calibration_candidates[chosen],'test':test_candidates[chosen],
        'raw_validation':robust.blend_predictions(predicted[MODES[0]][val],predicted[MODES[1]][val],w),
        'raw_test':robust.blend_predictions(predicted[MODES[0]][test],predicted[MODES[1]][test],w),
        'extras':extra_candidates[chosen]}
    return calibrated,{'selected_weight':w,'candidates':candidates,'selection_uses_test':False}

def run(max_folds=None):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'predictions').mkdir(exist_ok=True)
    pilot.HORIZONS=study.HORIZONS
    episodes=study.load('ait');cam,cam_audit=prepare_cam();episodes.update(cam)
    save_json('cam_source_audit.json',cam_audit)
    evidence=json.loads((VALIDATION/'endpoint_evidence.json').read_text())
    roots={r['scenario']:r['successful_root'] for r in evidence}
    folds=[];thresholds=[];scores=[];decisions=[];transfers=[];metadata=[];reproduction=[]
    for fold,test in enumerate(pilot.SCENARIOS):
        if max_folds is not None and fold>=max_folds:break
        val=pilot.SCENARIOS[(fold+1)%8];train=[n for n in pilot.SCENARIOS if n not in [val,test]]
        context=robust.prepare_context(episodes,train)
        for available in robust.SUBSETS:
            start=time.monotonic();key=robust.subset_key(available)
            extras=list(cam) if test=='fox' and available==('suricata','wazuh') else []
            predicted,bundle,details=robust.fit_predict(episodes,train,[val,test]+extras,available,context)
            # Natural/full and one-sensor baselines must reproduce prior exact fits.
            reference=('temporal_boosting' if len(available)==3 else
                'boosting_only_'+available[0] if len(available)==1 else None)
            if reference:
                with np.load(study.OUT/'predictions'/f'ait_{test}_{reference}.npz') as saved:
                    error=float(np.max(np.abs(predicted['available_boosting'][test]-saved['raw'])))
                assert error<1e-10,(test,key,error)
                reproduction.append({'test':test,'available':key,'reference':reference,'max_error':error})
            # Verify actual fitted output on a prefix, without onset or stage labels.
            probe={**episodes[val],'counts':episodes[val]['counts'][:23],'times':episodes[val]['times'][:23],
                'truth':np.full(23,999),'onset':-1}
            pp=robust.predict_model(bundle,probe,available)
            prefix_errors={m:float(np.max(np.abs(pp['risk'][m]-predicted[m][val][:23]))) for m in MODES[:2]}
            assert max(prefix_errors.values())<1e-10
            abstention=robust.predict_model(bundle,probe,[])
            assert abstention['risk'] is None
            pairs,selection=revised_pairs(episodes[val],predicted,val,test,extras)
            details.update(test=test,validation=val,train=train,blend=selection,
                prefix_max_errors=prefix_errors,no_sensor_status=abstention['status'])
            metadata.append(details)
            for mode,pair in pairs.items():
                row={'dataset':'ait','test':test,'validation':val,'train':train,'mode':mode,'available':key,
                    'status':'exploratory revised pipeline, not independent confirmation'}
                for label,vp,p in [('raw',pair['raw_validation'],pair['raw_test']),
                    ('calibrated',pair['validation'],pair['test'])]:
                    chosen=[select_threshold(episodes[val],vp[:,j],h,1) for j,h in enumerate(study.HORIZONS)]
                    row[label]={str(h):score(episodes[test],p[:,j],h,chosen[j]) for j,h in enumerate(study.HORIZONS)}
                folds.append(row)
                np.savez_compressed(OUT/'predictions'/f'ait_{test}_{key}_{mode}.npz',raw=pair['raw_test'],
                    calibrated=pair['test'],validation_raw=pair['raw_validation'],validation_calibrated=pair['validation'],
                    times=episodes[test]['times'],onset=episodes[test]['onset'],horizons=study.HORIZONS)
                for j,h in enumerate(study.HORIZONS):
                    for budget in BUDGETS:
                        threshold=select_threshold(episodes[val],pair['validation'][:,j],h,budget)
                        vm=score(episodes[val],pair['validation'][:,j],h,threshold)
                        thresholds.append({'test':test,'validation':val,'mode':mode,'available':key,'horizon':h,
                            'budget':budget,'threshold':threshold,'validation_metrics':vm})
                        for endpoint,onset in [('scheduled_onset',episodes[test]['onset']),('successful_root',roots[test])]:
                            ep={**episodes[test],'onset':onset}
                            for delay in ([0,1,2,5] if len(available)==3 else [0]):
                                p=delayed(pair['test'],delay)[:,j]
                                scores.append({'scenario':test,'mode':mode,'available':key,'horizon':h,'budget':budget,
                                    'endpoint':endpoint,'delay_minutes':delay,**score(ep,p,h,threshold)})
                        for n in extras:
                            transfers.append({'scenario':n,'mode':mode,'available':key,'horizon':h,'budget':budget,
                                'endpoint':'executed_privilege_tactic_proxy',**score(episodes[n],pair['extras'][n][:,j],h,threshold)})
                for damage in [10.,20.,50.]:
                    for effect in [.5,.8,1.]:
                        for disruption in [.5,1.,2.]:
                            aware=study.realized_decision_cost(episodes[test],pair['test'],True,damage,effect,disruption)
                            blind=study.realized_decision_cost(episodes[test],pair['test'],False,damage,effect,disruption)
                            decisions.append({'scenario':test,'mode':mode,'available':key,'damage':damage,
                                'effect_scale':effect,'disruption_scale':disruption,'delay_aware':aware,
                                'ignores_delay':blind,'improvement':blind['mean_assumed_cost']-aware['mean_assumed_cost'],
                                'status':'assumed framewise costs; no executed prevention'})
                for n in extras:
                    np.savez_compressed(OUT/'predictions'/f'cam_{n}_{mode}.npz',calibrated=pair['extras'][n],
                        times=episodes[n]['times'],onset=episodes[n]['onset'],horizons=study.HORIZONS)
            for name,values in [('fold_results.json',folds),('metadata.json',metadata),('thresholds.json',thresholds),
                ('scored.json',scores),('decisions.json',decisions),('cam_transfer.json',transfers),('baseline_reproduction.json',reproduction)]:
                save_json(name,values)
            print(f'Revised fold {fold+1}/8 {test} sensors={key}: {time.monotonic()-start:.1f}s, state weight={selection["selected_weight"]}',flush=True)
        del context
    print(f'Completed {len(metadata)} fitting/availability settings and {len(scores)} endpoint/budget/delay scores',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--max-folds',type=int);args=parser.parse_args()
    with threadpool_limits(limits=2):run(args.max_folds)

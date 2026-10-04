"""Fit nested campaign forecasts, then evaluate fixed selective-fusion variants."""
import argparse
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor,as_completed

import numpy as np
from threadpoolctl import threadpool_limits

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust
import selective_fusion as selective
from run_robust_forecasting import OUT as PREVIOUS,score
from audit_endpoints import OUT as VALIDATION,delayed
from comparison_audit import select_threshold,BUDGETS
from cam_transfer import prepare as prepare_cam

OUT=pilot.ROOT/'experiments/selective_fusion'


def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2),encoding='utf-8')


def cache_paths(train,available):
    name='+'.join(sorted(train))+'__'+robust.subset_key(available)
    return OUT/'inner_predictions'/(name+'.npz'),OUT/'inner_predictions'/(name+'.json')


def cache_signature():
    paths=[pilot.ROOT/'backend/research'/n for n in ['robust_forecasting.py','extended_study.py','evidence_pilot.py']]
    paths+=sorted((pilot.ROOT/'data/research/extended').glob('ait_*_v2.npz'))
    return {'version':1,'sha256':{str(p.relative_to(pilot.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def fit_inner_set(train_tuple,index,total,signature):
    episodes=study.load('ait')
    with threadpool_limits(limits=2):
        train=list(train_tuple);predict=[n for n in pilot.SCENARIOS if n not in train]
        context=None
        for available in robust.SUBSETS:
            path,meta_path=cache_paths(train,available)
            if path.exists() and meta_path.exists() and json.loads(meta_path.read_text())['cache_signature']==signature:
                continue
            start=time.monotonic()
            if context is None:context=robust.prepare_context(episodes,train)
            forecasts,bundle,meta=robust.fit_predict(episodes,train,predict,available,context)
            probe={**episodes[predict[0]],'counts':episodes[predict[0]]['counts'][:23],
                'times':episodes[predict[0]]['times'][:23],'truth':np.full(23,999),'onset':-1.}
            actual=robust.predict_model(bundle,probe,available)
            errors={mode:float(np.max(np.abs(actual['risk'][mode]-forecasts[mode][predict[0]][:23]))) for mode in forecasts}
            assert max(errors.values())<1e-10
            meta.update(train=train,predicted_campaigns=predict,prefix_errors=errors,cache_signature=signature)
            np.savez_compressed(path,**{n+'__'+mode:p for mode,values in forecasts.items() for n,p in values.items()})
            meta_path.write_text(json.dumps(meta,indent=2),encoding='utf-8')
            print(f'Inner fitting set {index+1}/{total}, {robust.subset_key(available)}: {time.monotonic()-start:.1f}s',flush=True)
            del bundle,forecasts
        del context


def prepare_inner(episodes,max_sets=None,workers=4):
    signature=cache_signature();sets=set()
    for i,test in enumerate(pilot.SCENARIOS):
        val=pilot.SCENARIOS[(i+1)%8];train=[n for n in pilot.SCENARIOS if n not in [test,val]]
        sets.update(tuple(sorted(set(train)-{n})) for n in train)
    fitting_sets=sorted(sets)[:max_sets]
    if workers==1:
        for i,train in enumerate(fitting_sets):fit_inner_set(train,i,len(sets),signature)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(fit_inner_set,train,i,len(sets),signature) for i,train in enumerate(fitting_sets)]
            for future in as_completed(futures):future.result()


def load_inner(train,held,available):
    path,_=cache_paths([n for n in train if n!=held],available)
    with np.load(path) as saved:return (saved[held+'__available_boosting'].copy(),saved[held+'__state_augmented_boosting'].copy())


def evaluate(episodes):
    cam,cam_audit=prepare_cam();episodes.update(cam);save('cam_source_audit.json',cam_audit)
    roots={r['scenario']:r['successful_root'] for r in json.loads((VALIDATION/'endpoint_evidence.json').read_text())}
    metadata=[];thresholds=[];scored=[];decisions=[];transfers=[]
    for i,test in enumerate(pilot.SCENARIOS):
        val=pilot.SCENARIOS[(i+1)%8];train=[n for n in pilot.SCENARIOS if n not in [test,val]]
        start=time.monotonic()
        for available in robust.SUBSETS:
            key=robust.subset_key(available);held={n:load_inner(train,n,available) for n in train}
            weights,selection=selective.select_weights(episodes,held,train)
            fitting_inputs={'pooled_counts':{n:held[n][0] for n in train},
                'pooled_state':{n:held[n][1] for n in train},
                'pooled_fixed_blend':{n:selective.mix(*held[n],np.full(6,.25)) for n in train},
                'pooled_selective':{n:selective.mix(*held[n],weights) for n in train}}
            calibrators={mode:selective.fit_calibration(episodes,p,train) for mode,p in fitting_inputs.items()}
            outer={}
            for label,mode in [('base','available_boosting'),('state','state_augmented_boosting')]:
                with np.load(PREVIOUS/'predictions'/f'ait_{test}_{key}_{mode}.npz') as saved:
                    outer[label]={'test':saved['raw'].copy(),'validation':saved['validation_raw'].copy()}
            forecast=selective.predict_pair(outer['base']['test'],outer['state']['test'],weights,calibrators)
            validation=selective.predict_pair(outer['base']['validation'],outer['state']['validation'],weights,calibrators)
            extras=list(cam) if test=='fox' and available==('suricata','wazuh') else []
            extra_forecasts={}
            # Reconstruct raw six-fitting-campaign CAM predictions using the unchanged expert.
            if extras:
                context=robust.prepare_context(episodes,train)
                raw,bundle,_=robust.fit_predict(episodes,train,extras,available,context)
                for n in extras:extra_forecasts[n]=selective.predict_pair(raw['available_boosting'][n],raw['state_augmented_boosting'][n],weights,calibrators)
                del context,bundle,raw
            contribution={str(h):{'selected_weight':weights[j],
                'raw_changed_minutes':int(np.sum(np.abs(forecast['raw_selective'][:,j]-forecast['raw_counts'][:,j])>1e-12)),
                'calibrated_changed_minutes':int(np.sum(np.abs(forecast['pooled_selective'][:,j]-forecast['pooled_counts'][:,j])>1e-12))}
                for j,h in enumerate(study.HORIZONS)}
            metadata.append({'test':test,'validation':val,'train':train,'available':key,
                'weights':weights,'selection':selection,'calibrators':calibrators,'state_contribution':contribution,
                'selection_uses_test':False,'calibration_uses_outer_validation':False,
                'fitting_forecast_campaigns':train,'no_sensor_status':'insufficient_sensors'})
            for mode in selective.MODES:
                p=forecast[mode];vp=validation[mode]
                np.savez_compressed(OUT/'predictions'/f'ait_{test}_{key}_{mode}.npz',risk=p,validation_risk=vp,
                    times=episodes[test]['times'],onset=episodes[test]['onset'],horizons=study.HORIZONS)
                for j,h in enumerate(study.HORIZONS):
                    for budget in BUDGETS:
                        threshold=select_threshold(episodes[val],vp[:,j],h,budget)
                        thresholds.append({'test':test,'validation':val,'mode':mode,'available':key,'horizon':h,
                            'budget':budget,'threshold':threshold,'validation_metrics':score(episodes[val],vp[:,j],h,threshold)})
                        for endpoint,onset in [('scheduled_onset',episodes[test]['onset']),('successful_root',roots[test])]:
                            ep={**episodes[test],'onset':onset}
                            for delay in ([0,1,2,5] if len(available)==3 else [0]):
                                scored.append({'scenario':test,'mode':mode,'available':key,'horizon':h,'budget':budget,
                                    'endpoint':endpoint,'delay_minutes':delay,**score(ep,delayed(p,delay)[:,j],h,threshold)})
                        for n in extras:
                            transfers.append({'scenario':n,'mode':mode,'available':key,'horizon':h,'budget':budget,
                                'endpoint':'executed_privilege_tactic_proxy',**score(episodes[n],extra_forecasts[n][mode][:,j],h,threshold)})
                for damage in [10.,20.,50.]:
                    for effect in [.5,.8,1.]:
                        for disruption in [.5,1.,2.]:
                            aware=study.realized_decision_cost(episodes[test],p,True,damage,effect,disruption)
                            blind=study.realized_decision_cost(episodes[test],p,False,damage,effect,disruption)
                            decisions.append({'scenario':test,'mode':mode,'available':key,'damage':damage,
                                'effect_scale':effect,'disruption_scale':disruption,'delay_aware':aware,'ignores_delay':blind,
                                'improvement':blind['mean_assumed_cost']-aware['mean_assumed_cost'],'status':'assumed costs; no intervention'})
                for n in extras:
                    np.savez_compressed(OUT/'predictions'/f'cam_{n}_{mode}.npz',risk=extra_forecasts[n][mode],
                        times=episodes[n]['times'],onset=episodes[n]['onset'],horizons=study.HORIZONS)
            for name,values in [('metadata.json',metadata),('thresholds.json',thresholds),('scored.json',scored),
                ('decisions.json',decisions),('cam_transfer.json',transfers)]:save(name,values)
        print(f'Selective outer fold {i+1}/8 {test}: {time.monotonic()-start:.1f}s',flush=True)


def run(inner_only=False,max_sets=None,workers=4):
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ['inner_predictions','predictions']:(OUT/name).mkdir(exist_ok=True)
    pilot.HORIZONS=study.HORIZONS;episodes=study.load('ait')
    prepare_inner(episodes,max_sets,workers)
    if not inner_only:evaluate(episodes)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inner-only',action='store_true');parser.add_argument('--max-sets',type=int)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.max_sets is not None and not args.inner_only:parser.error('--max-sets requires --inner-only')
    if not 1<=args.workers<=8:parser.error('--workers must be between 1 and 8')
    with threadpool_limits(limits=2):run(args.inner_only,args.max_sets,args.workers)

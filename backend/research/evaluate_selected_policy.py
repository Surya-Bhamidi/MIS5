"""Choose on archived outer validation, then score original outer-test forecasts."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))

import numpy as np
import extended_study as study
from app.models.warning_policy import WarningConfig
from evaluate_improvements import metrics
from select_warning_policy import choose_policy,trace,guardrails,candidates

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'
CURRENT=ROOT/'experiments/current_version'
FULL='aminer+suricata+wazuh'


def run():
    episodes=study.load('ait')
    roots={r['scenario']:r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text())}
    metadata=json.loads((CURRENT/'metadata.json').read_text())
    thresholds=json.loads((CURRENT/'thresholds.json').read_text())
    rows=[];selections=[];hashes={}
    immediate=candidates()[0][1]
    for fold in metadata:
        name,val,key=fold['test'],fold['validation'],fold['available']
        path=CURRENT/'predictions'/f'ait_{name}_{key}_pooled_fixed_blend.npz'
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path,allow_pickle=False) as data:
            # Copy validation only for selection; test arrays are loaded later.
            validation=data['validation_risk'].copy();horizons=data['horizons'].tolist()
        for horizon in (15,30):
            j=horizons.index(horizon)
            threshold=next(r['threshold'] for r in thresholds if r['test']==name and r['available']==key and r['horizon']==horizon and r['budget']==1)
            choice=choose_policy(episodes[val]['times'],validation[:,j],roots[val],horizon,threshold)
            selection={**choice,'test':name,'validation':val,'available':key,'horizon':horizon,
                       'selection_uses_outer_test':False,'threshold':threshold}
            selections.append(selection)
            with np.load(path,allow_pickle=False) as data:
                mask=data['times']<roots[name]
                times=data['times'][mask];scores=data['risk'][mask,j]
            modes={}
            for mode,config in [('baseline',immediate),('previous',WarningConfig()),('selected',WarningConfig(**choice['config']))]:
                warning,notifications=trace(times,scores,threshold,config)
                modes[mode]=metrics(times,roots[name],horizon,warning,notifications)
            rows.append(dict(campaign=name,validation=val,available=key,horizon=horizon,policy=choice['name'],
                             brier=float(np.mean((scores-(times+horizon*60>=roots[name]))**2)),
                             test_guardrail_regressions=guardrails(modes['baseline'],modes['selected']),**modes))
    summary=[]
    for key in sorted({r['available'] for r in rows}):
        for horizon in (15,30):
            group=[r for r in rows if r['available']==key and r['horizon']==horizon]
            entry=dict(available=key,horizon=horizon,campaigns=len(group),
                       selected_policies=dict(Counter(r['policy'] for r in group)))
            for mode in ('baseline','previous','selected'):
                entry[mode]={k:sum(r[mode][k] for r in group) for k in ('timely_notification','timely_warning_episode','false_notifications','false_warning_episodes','negative_warning_minutes','notifications')}
                leads=[r[mode]['notification_lead_minutes'] for r in group if r[mode]['notification_lead_minutes'] is not None]
                entry[mode]['mean_notification_lead_minutes']=float(np.mean(leads)) if leads else None
            entry['test_regressions']=[dict(campaign=r['campaign'],metrics=r['test_guardrail_regressions']) for r in group if r['test_guardrail_regressions']]
            entry['mean_brier_unchanged']=float(np.mean([r['brier'] for r in group]))
            summary.append(entry)
    paths=[Path(__file__),ROOT/'backend/research/select_warning_policy.py',ROOT/'backend/app/models/warning_policy.py',
           ROOT/'backend/research/evaluate_improvements.py',OUT/'SELECTION_PROTOCOL.md',CURRENT/'metadata.json',CURRENT/'thresholds.json',
           ROOT/'experiments/publication_validation/endpoint_evidence.json']
    for path in paths:hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in episodes:
        path=ROOT/'data/research/extended'/f'ait_{name}_v2.npz'
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    result=dict(scope='Validation-selected policy on previously inspected research folds; no independent confirmation',
                selection_uses_outer_test=False,protocol='SELECTION_PROTOCOL.md',summary=summary,campaigns=rows)
    OUT.mkdir(parents=True,exist_ok=True)
    for filename,value in [('selected_evaluation.json',result),('policy_selection.json',selections),('selection_inputs.json',hashes)]:
        (OUT/filename).write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps([r for r in summary if r['available']==FULL],indent=2))
    return result


if __name__=='__main__':run()

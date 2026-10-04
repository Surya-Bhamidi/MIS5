"""Audit successful AIT outcomes and rescore frozen forecasts without retraining."""
import csv
import hashlib
import json
import re
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import average_precision_score

import evidence_pilot as pilot
import extended_study as study
from fetch_endpoint_evidence import DEST

OUT=pilot.ROOT/'experiments/publication_validation'

def audit_sessions(lines,annotations):
    sessions=[]
    for item in annotations:
        if 'escalate' not in item['labels']:continue
        number=item['line']
        if not 1<=number<=len(lines):raise ValueError('Invalid published audit line index')
        text=lines[number-1]
        if not (text.startswith('type=USER_START ') and 'res=success' in text):continue
        if not re.search(r'exe="/(?:usr/)?bin/(?:su|sudo)"',text):continue
        timestamp=re.search(r'msg=audit\(([0-9.]+):',text)
        account=re.search(r'acct="([^"]+)"',text)
        if timestamp and account:
            sessions.append({'timestamp':float(timestamp[1]),'account':account[1],
                'line':number,'audit_record':text,'labels':item['labels']})
    sessions.sort(key=lambda r:r['timestamp'])
    return sessions

def endpoints():
    episodes=study.load('ait')
    manifest=json.loads((DEST/'manifest.json').read_text())
    rows=[]
    for name,ep in episodes.items():
        for member in manifest[name]['members']:
            content=(pilot.ROOT/member['local_path']).read_bytes()
            if hashlib.sha256(content).hexdigest()!=member['sha256']:
                raise ValueError('Endpoint evidence checksum mismatch')
        folder=DEST/name
        lines=(folder/'intranet_audit.log').read_text().splitlines()
        annotations=[json.loads(line) for line in (folder/'intranet_audit_labels.jsonl').read_text().splitlines()]
        sessions=audit_sessions(lines,annotations)
        if not sessions:raise ValueError(f'Missing successful change-user evidence: {name}')
        root=next((s for s in sessions if s['account']=='root'),None)
        execution=[]
        for line in (folder/'attacks.log').read_text().splitlines():
            if line.endswith(' login_user'):
                execution.append(datetime.fromisoformat(line.rsplit(' ',1)[0]).timestamp())
        if len(execution)!=1:raise ValueError(f'Ambiguous executed login: {name}')
        rows.append({'scenario':name,'scheduled_onset':ep['onset'],'executed_login':execution[0],
            'successful_change_user':sessions[0]['timestamp'],
            'successful_root':None if root is None else root['timestamp'],
            'execution_offset_seconds':execution[0]-ep['onset'],
            'change_user_offset_seconds':sessions[0]['timestamp']-ep['onset'],
            'root_offset_seconds':None if root is None else root['timestamp']-ep['onset'],
            'change_user_proof':sessions[0],'root_proof':root})
    return rows

def strict_warning_metrics(ep,p,horizon,threshold):
    result=pilot.warning_metrics(ep,p,horizon,threshold)
    mask=pilot.preonset(ep);warning=p[mask]>=threshold
    starts=np.flatnonzero(warning&~np.r_[False,warning[:-1]])
    valid=starts[pilot.targets(ep,horizon)[mask][starts]==1]
    result.update(strict_warning_recall=int(len(valid)>0),strict_lead_minutes=None if not len(valid)
        else float((ep['onset']-ep['times'][mask][valid[0]])/60))
    return result

def delayed(p,minutes):
    if minutes==0:return p.copy()
    result=np.zeros_like(p)
    if minutes<len(p):result[minutes:]=p[:-minutes]
    return result

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    pilot.HORIZONS=study.HORIZONS
    audited=endpoints()
    (OUT/'endpoint_evidence.json').write_text(json.dumps(audited,indent=2),encoding='utf-8')
    with (OUT/'endpoint_offsets.csv').open('w',newline='',encoding='utf-8') as f:
        fields=[k for k in audited[0] if not k.endswith('_proof')]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:r[k] for k in fields} for r in audited)
    episodes=study.load('ait')
    folds=[]
    for filename in ['ait_fold_results.json','fusion_fold_results.json','ablation_fold_results.json']:
        folds+=json.loads((study.OUT/filename).read_text())
    for filename in ['published_hmm_fold_results.json','gru_fold_results.json']:
        if (OUT/filename).exists():folds+=json.loads((OUT/filename).read_text())
    scored=[]
    for fold in folds:
        name=fold['test'];ep=episodes[name];audit=next(r for r in audited if r['scenario']==name)
        prediction_root=OUT if fold['mode'].startswith(('perera','ansari')) else study.OUT
        with np.load(prediction_root/'predictions'/f"ait_{name}_{fold['mode']}.npz") as saved:
            original=saved['calibrated'].copy()
        for endpoint in ['scheduled_onset','successful_change_user','successful_root']:
            if audit[endpoint] is None:continue
            updated={**ep,'onset':audit[endpoint]}
            for delay in [0,1,2,5]:
                p=delayed(original,delay)
                for j,h in enumerate(study.HORIZONS):
                    threshold=fold['calibrated'][str(h)]['threshold']
                    metrics=strict_warning_metrics(updated,p[:,j],h,threshold)
                    mask=pilot.preonset(updated);y=pilot.targets(updated,h)[mask]
                    metrics.update(brier=float(np.mean((p[mask,j]-y)**2)),
                        average_precision=float(average_precision_score(y,p[mask,j])))
                    scored.append({'scenario':name,'mode':fold['mode'],'endpoint':endpoint,
                                   'delay_minutes':delay,'horizon':h,**metrics})
    (OUT/'endpoint_rescored.json').write_text(json.dumps(scored,indent=2),encoding='utf-8')
    with (OUT/'endpoint_rescored.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(scored[0]));writer.writeheader();writer.writerows(scored)
    aggregate=[]
    for mode in sorted({r['mode'] for r in scored}):
        for endpoint in ['scheduled_onset','successful_change_user','successful_root']:
            for delay in [0,1,2,5]:
                for horizon in study.HORIZONS:
                    subset=[r for r in scored if (r['mode'],r['endpoint'],r['delay_minutes'],r['horizon'])
                        ==(mode,endpoint,delay,horizon)]
                    if not subset:continue
                    leads=[r['strict_lead_minutes'] for r in subset if r['strict_lead_minutes'] is not None]
                    aggregate.append({'mode':mode,'endpoint':endpoint,'delay_minutes':delay,'horizon':horizon,
                        'campaigns':len(subset),'warned':sum(r['warning_recall'] for r in subset),
                        'strict_warned':sum(r['strict_warning_recall'] for r in subset),
                        'false_episodes':sum(r['false_warning_episodes'] for r in subset),
                        'negative_warning_minutes':sum(r['negative_warning_minutes'] for r in subset),
                        'mean_brier':float(np.mean([r['brier'] for r in subset])),
                        'mean_ap':float(np.mean([r['average_precision'] for r in subset])),
                        'median_strict_lead':None if not leads else float(np.median(leads))})
    (OUT/'endpoint_summary.json').write_text(json.dumps(aggregate,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in row.items() if not k.endswith('_proof')} for row in audited],indent=2),flush=True)
    for r in aggregate:
        if r['mode'] in ['temporal_boosting','conditional_fusion','equal_fusion'] and r['horizon']==15 and r['delay_minutes']==0:
            print(json.dumps(r),flush=True)

if __name__=='__main__':run()

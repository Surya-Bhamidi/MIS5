"""Independent consistency checks for the additional comparison outputs."""
import json
import hashlib
from datetime import datetime,timezone

import numpy as np
from sklearn.metrics import average_precision_score

import evidence_pilot as pilot
import extended_study as study
from audit_endpoints import OUT as VALIDATION
from competitive_gru import OUT,MODE,CHECKPOINTS
from comparison_audit import folds,BUDGETS,HORIZONS

def metrics(ep,p,h,threshold):
    mask=ep['times']<ep['onset'];times=ep['times'][mask];scores=p[mask]
    y=((ep['onset']-times)<=h*60).astype(int)
    active=scores>=threshold
    starts=[i for i in range(len(active)) if active[i] and (i==0 or not active[i-1])]
    good=[i for i in starts if y[i]]
    false=sum(1 for i in starts if not y[i])
    negative=int(np.sum(y==0));lead=None if not good else float((ep['onset']-times[good[0]])/60)
    return {'brier':float(np.mean((scores-y)**2)),
        'average_precision':float(average_precision_score(y,scores)),
        'strict_warning_recall':int(bool(good)),
        'warning_recall':int(any(active[i] and y[i] for i in range(len(active)))),
        'strict_lead_minutes':lead,'false_warning_episodes':false,
        'negative_warning_minutes':int(np.sum(active&(y==0))),
        'false_warnings_per_24h':false/max(negative/60,1e-9)*24}

def compare(record,recomputed):
    for k,v in recomputed.items():
        if v is None:assert record[k] is None,(k,record[k])
        else:assert abs(record[k]-v)<1e-12,(k,record[k],v)

def run():
    episodes=study.load('ait');metadata=json.loads((OUT/'gru_metadata.json').read_text())
    assert len(metadata)==8 and {r['test'] for r in metadata}==set(episodes)
    sources={};prediction={}
    for directory,r in folds():
        key=(r['test'],r['mode']);sources[key]=(directory,r)
        with np.load(directory/'predictions'/f'ait_{key[0]}_{key[1]}.npz') as saved:
            prediction[key]={k:saved[k].copy() for k in ['raw','calibrated','validation_raw','validation_calibrated']}
        assert len(r['train'])==6 and not set(r['train'])&{r['test'],r['validation']}
        assert pilot.SCENARIOS[(pilot.SCENARIOS.index(r['test'])+1)%8]==r['validation']
        for p in prediction[key].values():
            assert np.isfinite(p).all() and np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
    assert len(sources)==15*8
    for r in metadata:
        candidates=r['candidates'];assert tuple(c['epoch'] for c in candidates)==CHECKPOINTS
        best=max(candidates,key=lambda c:(c['selection_score'],-c['epoch']))
        assert r['selected_epoch']==best['epoch'] and len(r['training_loss'])==18
        vp=prediction[(r['test'],MODE)]['validation_raw'];ep=episodes[r['validation']]
        mask=ep['times']<ep['onset']
        for h in HORIZONS:
            y=((ep['onset']-ep['times'][mask])<=h*60).astype(int)
            assert abs(average_precision_score(y,vp[mask,study.HORIZONS.index(h)])-best['validation_ap'][str(h)])<1e-12
        assert r['prefix_max_error']<1e-7
        ep=episodes[r['test']];fold=sources[(r['test'],MODE)][1]
        for label in ['raw','calibrated']:
            for j,h in enumerate(study.HORIZONS):
                record=fold[label][str(h)]
                compare(record,metrics(ep,prediction[(r['test'],MODE)][label][:,j],h,record['threshold']))
    roots={r['scenario']:r['successful_root'] for r in json.loads((VALIDATION/'endpoint_evidence.json').read_text())}
    selected=json.loads((OUT/'threshold_selection.json').read_text());lookup={}
    assert len(selected)==15*8*len(HORIZONS)*len(BUDGETS)
    for r in selected:
        key=(r['test'],r['mode']);vp=prediction[key]['validation_calibrated'][:,study.HORIZONS.index(r['horizon'])]
        rec=metrics(episodes[r['validation']],vp,r['horizon'],r['threshold'])
        compare(r['validation_metrics'],{k:v for k,v in rec.items() if k not in ['brier','average_precision']})
        assert rec['false_warnings_per_24h']<=r['budget']+1e-12 and rec['negative_warning_minutes']<=5
        lookup[(r['test'],r['mode'],r['horizon'],r['budget'])]=r['threshold']
    rows=json.loads((OUT/'budget_fold_results.json').read_text());assert len(rows)==1920
    for r in rows:
        ep=episodes[r['scenario']]
        if r['endpoint']=='successful_root':ep={**ep,'onset':roots[r['scenario']]}
        p=prediction[(r['scenario'],r['mode'])]['calibrated'][:,study.HORIZONS.index(r['horizon'])]
        threshold=lookup[(r['scenario'],r['mode'],r['horizon'],r['budget'])]
        assert threshold==r['threshold'];compare(r,metrics(ep,p,r['horizon'],threshold))
    original=json.loads((OUT/'original_threshold_scores.json').read_text());assert len(original)==480
    for r in original:
        key=(r['scenario'],r['mode']);ep=episodes[r['scenario']]
        if r['endpoint']=='successful_root':ep={**ep,'onset':roots[r['scenario']]}
        threshold=sources[key][1]['calibrated'][str(r['horizon'])]['threshold']
        compare(r,metrics(ep,prediction[key]['calibrated'][:,study.HORIZONS.index(r['horizon'])],r['horizon'],threshold))
    manifest=json.loads((pilot.ROOT/'third_party/pard_ssm/SOURCE_MANIFEST.json').read_text())
    for name,sha in manifest['files'].items():
        assert hashlib.sha256((pilot.ROOT/'third_party/pard_ssm'/name).read_bytes()).hexdigest()==sha
    result={'passed':True,'gru_folds':8,'models':15,'budget_test_rows':len(rows),
        'validation_thresholds':len(selected),'original_threshold_rows':len(original),
        'checks':['split separation','selected epoch matches validation-only AP',
            'finite bounded monotone predictions','all validation budget constraints',
            'independent episode starts, false episodes, lead, AP and Brier',
            'test thresholds equal frozen validation selections','pinned author-source SHA-256'],
        'utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':run()

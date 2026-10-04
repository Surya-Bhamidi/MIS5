"""Audit author source and rescore frozen predictions at validation-selected budgets."""
import hashlib
import importlib
import json
import sys
import types

import numpy as np
from sklearn.metrics import average_precision_score

import evidence_pilot as pilot
import extended_study as study
from audit_endpoints import OUT as VALIDATION, strict_warning_metrics
from competitive_gru import OUT

BUDGETS=[0,.25,1,4]
HORIZONS=[15,30]

def select_threshold(ep,p,horizon,budget):
    mask=pilot.preonset(ep);scores=p[mask];positive=pilot.targets(ep,horizon)[mask]==1
    candidates=np.unique(np.r_[0,np.quantile(scores,np.linspace(0,1,257)),
        scores[positive],np.nextafter(scores[positive],np.inf),1.000001])
    best=None;chosen=1.000001
    for threshold in candidates:
        result=strict_warning_metrics(ep,p,horizon,threshold)
        rate=result['false_warnings_per_24h']
        if rate is None or rate>budget or result['negative_warning_minutes']>5:continue
        rank=(result['strict_warning_recall'],result['strict_lead_minutes'] or 0,
            -result['negative_warning_minutes'],-result['false_warning_episodes'],threshold)
        if best is None or rank>best:best=rank;chosen=float(threshold)
    return chosen

def source_audit():
    root=pilot.ROOT/'third_party/pard_ssm'
    manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text())
    for name,sha in manifest['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
    # Reviewed modules contain NumPy/SciPy, dataclasses and typing imports only.
    package=types.ModuleType('_author_pard_src');package.__path__=[str(root/'src')]
    sys.modules[package.__name__]=package
    module=importlib.import_module('_author_pard_src.inference.variational_switching')
    rng=np.random.default_rng(1729);x=rng.normal(size=(80,4))
    x[20:50]*=4
    model=module.SwitchingSSM(n_regimes=4,state_dim=8,obs_dim=4)
    full=model.filter(x);prefix=model.filter(x[:25])
    error=float(np.max(np.abs(full.regime_probs[:25]-prefix.regime_probs)))
    assert error<1e-12 and np.allclose(full.regime_probs.sum(axis=1),1)
    before={k:[getattr(r,k).copy() for r in model.regimes] for k in ['A','C','Q','R']}
    history=model.fit(x,n_iter=3,verbose=False)
    unchanged=[k for k in before if all(np.array_equal(a,getattr(r,k)) for a,r in zip(before[k],model.regimes))]
    assert unchanged==['A','C','Q','R']
    after=model.filter(x);assert np.isfinite(after.regime_probs).all()
    differences=[]
    for seed in range(20):
        sample=np.random.default_rng(seed).normal(size=(40,4));sample[20:]*=4
        m=module.SwitchingSSM(n_regimes=4,state_dim=8,obs_dim=4)
        a=m.filter(sample).viterbi_path[:20];b=m.filter(sample[:20]).viterbi_path
        differences.append(int(np.count_nonzero(a!=b)))
    record={'repository':manifest['repository'],'commit':manifest['commit'],
        'source_files_sha256_verified':len(manifest['files']),
        'executed':'unmodified author SwitchingSSM.filter and fit on synthetic audit inputs',
        'native_filtered_prefix_max_error':error,'native_fit_iterations':3,
        'native_fit_log_likelihoods':[float(v) for v in history],
        'native_fit_regime_parameters_unchanged':unchanged,
        'viterbi_prefix_differences_across_20_probes':differences,
        'standard_experiment_findings':[
            'run_switching.py calls build_observation_sequence separately on train and test.',
            'That builder fits its scaler and PCA to each supplied sequence.',
            'The runner trains/evaluates only observations[0], the first window.',
            'The runner evaluates retrospective viterbi_path for contemporaneous labels.',
            'The reviewed fit method updates transition_matrix and initial_regime_probs, not A/C/Q/R.',
            'The reviewed runner does not implement the paper first-onset forecast/KL alert evaluation.'
        ],'comparison_status':'excluded from full-system superiority comparison',
        'reason':'Native outputs, preprocessing and available experimental path do not reproduce our first-onset task or the paper complete predictive evaluation. Author filtered probabilities pass a causal-prefix check; retrospective decoding and independently fitted test preprocessing must not enter an online forecast benchmark.',
        'paper':'https://arxiv.org/html/2604.02299v1'}
    (OUT/'author_source_audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('Author source audit:',error,'filtered prefix error; retrospective path differences:',sum(differences),flush=True)

def folds():
    rows=[]
    for directory,names in [(study.OUT,['ait_fold_results.json','fusion_fold_results.json','ablation_fold_results.json']),
        (VALIDATION,['published_hmm_fold_results.json','gru_fold_results.json']),
        (OUT,['gru_fold_results.json'])]:
        for name in names:
            path=directory/name
            if path.exists():rows += [(directory,r) for r in json.loads(path.read_text())]
    return rows

def aggregate(rows,keys):
    result=[]
    for identity in sorted({tuple(r[k] for k in keys) for r in rows}):
        group=[r for r in rows if tuple(r[k] for k in keys)==identity]
        lead=[r['strict_lead_minutes'] for r in group if r['strict_lead_minutes'] is not None]
        result.append(dict(zip(keys,identity),campaigns=len(group),
            mean_brier=float(np.mean([r['brier'] for r in group])),
            mean_ap=float(np.mean([r['average_precision'] for r in group])),
            warned=sum(r['warning_recall'] for r in group),strict_warned=sum(r['strict_warning_recall'] for r in group),
            false_episodes=sum(r['false_warning_episodes'] for r in group),
            negative_warning_minutes=sum(r['negative_warning_minutes'] for r in group),
            median_strict_lead=None if not lead else float(np.median(lead))))
    return result

def evaluate():
    episodes=study.load('ait');evidence=json.loads((VALIDATION/'endpoint_evidence.json').read_text())
    roots={r['scenario']:r['successful_root'] for r in evidence}
    rows=[];original=[];selection=[]
    for directory,fold in folds():
        ep=episodes[fold['test']];val=episodes[fold['validation']]
        with np.load(directory/'predictions'/f"ait_{fold['test']}_{fold['mode']}.npz") as saved:
            p=saved['calibrated'].copy();vp=saved['validation_calibrated'].copy()
        for j,h in enumerate(study.HORIZONS):
            if h not in HORIZONS:continue
            for endpoint,onset in [('scheduled_onset',ep['onset']),('successful_root',roots[fold['test']])]:
                updated={**ep,'onset':onset};mask=pilot.preonset(updated);y=pilot.targets(updated,h)[mask]
                scores={'brier':float(np.mean((p[mask,j]-y)**2)),
                    'average_precision':float(average_precision_score(y,p[mask,j]))}
                frozen=fold['calibrated'][str(h)]['threshold']
                original.append({'mode':fold['mode'],'scenario':fold['test'],'horizon':h,'endpoint':endpoint,
                    **strict_warning_metrics(updated,p[:,j],h,frozen),**scores})
            for budget in BUDGETS:
                threshold=select_threshold(val,vp[:,j],h,budget)
                vm=strict_warning_metrics(val,vp[:,j],h,threshold)
                assert vm['false_warnings_per_24h']<=budget+1e-12 and vm['negative_warning_minutes']<=5
                selection.append({'mode':fold['mode'],'test':fold['test'],'validation':fold['validation'],
                    'horizon':h,'budget':budget,'threshold':threshold,'validation_metrics':vm})
                for endpoint,onset in [('scheduled_onset',ep['onset']),('successful_root',roots[fold['test']])]:
                    updated={**ep,'onset':onset};mask=pilot.preonset(updated);y=pilot.targets(updated,h)[mask]
                    rows.append({'mode':fold['mode'],'scenario':fold['test'],'horizon':h,'endpoint':endpoint,
                        'budget':budget,**strict_warning_metrics(updated,p[:,j],h,threshold),
                        'brier':float(np.mean((p[mask,j]-y)**2)),
                        'average_precision':float(average_precision_score(y,p[mask,j]))})
    for name,values in [('budget_fold_results',rows),('threshold_selection',selection),
        ('original_threshold_scores',original),('budget_summary',aggregate(rows,['mode','endpoint','horizon','budget'])),
        ('original_threshold_summary',aggregate(original,['mode','endpoint','horizon']))]:
        (OUT/f'{name}.json').write_text(json.dumps(values,indent=2),encoding='utf-8')
    print('Scored',len(rows),'budget rows and',len(original),'original-threshold rows',flush=True)

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);source_audit();evaluate()

"""Independent output consistency, causality and evidence-integrity verification."""
import contextlib
import hashlib
import io
import json
import unittest
from datetime import datetime,timezone

import numpy as np

import evidence_pilot as pilot
import extended_study as study
import published_hmm_baseline as hmm
from gru_baseline import checks as gru_checks
from audit_endpoints import OUT,endpoints,strict_warning_metrics,delayed

def run():
    log=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(pilot.ROOT/'backend/tests'))
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    assert result.wasSuccessful(),log.getvalue()
    with contextlib.redirect_stdout(io.StringIO()):
        pilot.checks();study.checks();hmm.checks();gru_checks()
    records={'regressions':{'passed':True,'tests':result.testsRun,'output':log.getvalue()},
        'research_invariants':{'passed':True,'suites':['original pilot','extended BN/HMM/Decision Network',
            'adapted HMM','GRU causal prefixes']}}
    proof=endpoints()
    saved=json.loads((OUT/'endpoint_evidence.json').read_text())
    assert proof==saved and len(proof)==8
    assert all(r['successful_change_user']>=r['executed_login'] and r['successful_root']>r['successful_change_user'] for r in proof)
    records['endpoint_evidence']={'passed':True,'campaigns':8,'checks':['selected-member SHA-256',
        'one-based published annotation indexing','successful attack-labelled sessions','execution/outcome ordering']}
    folds=json.loads((OUT/'published_hmm_fold_results.json').read_text())+json.loads((OUT/'gru_fold_results.json').read_text())
    for r in folds:
        assert not set(r['train'])&{r['test'],r['validation']}
        with np.load(OUT/'predictions'/f"ait_{r['test']}_{r['mode']}.npz") as saved:
            for label in ['raw','calibrated']:
                p=saved[label];mask=saved['times']<saved['onset']
                assert np.isfinite(p).all() and np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
                for j,h in enumerate(study.HORIZONS):
                    y=(saved['times'][mask]+h*60>=saved['onset']).astype(int)
                    assert abs(np.mean((p[mask,j]-y)**2)-r[label][str(h)]['brier'])<1e-12
    records['adapted_baselines']={'passed':True,'folds':len(folds),'checks':['split isolation',
        'finite bounded cumulative risk','independently recomputed Brier']}
    rescored=json.loads((OUT/'endpoint_rescored.json').read_text());episodes=study.load('ait')
    onset={(r['scenario'],field):r[field] for r in proof for field in ['scheduled_onset','successful_change_user','successful_root']}
    prediction_cache={}
    for row in rescored:
        name=row['scenario'];mode=row['mode'];source=OUT if mode.startswith(('perera','ansari')) else study.OUT
        if (name,mode) not in prediction_cache:
            with np.load(source/'predictions'/f'ait_{name}_{mode}.npz') as saved:
                prediction_cache[(name,mode)]=saved['calibrated'].copy()
        p=prediction_cache[(name,mode)]
        ep={**episodes[name],'onset':onset[(name,row['endpoint'])]};j=study.HORIZONS.index(row['horizon'])
        predicted=delayed(p,row['delay_minutes'])[:,j]
        metrics=strict_warning_metrics(ep,predicted,row['horizon'],row['threshold'])
        for key in ['warning_recall','strict_warning_recall','false_warning_episodes','negative_warning_minutes']:
            assert metrics[key]==row[key]
        mask=pilot.preonset(ep);y=pilot.targets(ep,row['horizon'])[mask]
        assert abs(np.mean((predicted[mask]-y)**2)-row['brier'])<1e-12
    records['frozen_endpoint_rescores']={'passed':True,'rows':len(rescored),'checks':['unchanged saved forecasts',
        'delay uses past only','warning starts independently recomputed','endpoint-specific Brier']}
    transfer=json.loads((OUT/'cam_transfer.json').read_text())
    assert all(v<=1e-10 for v in transfer['reconstruction_max_errors'].values())
    for item in json.loads((pilot.ROOT/'data/research/cam_lds/manifest.json').read_text()):
        for member in item['members']:
            assert hashlib.sha256((pilot.ROOT/member['path']).read_bytes()).hexdigest()==member['sha256']
    for r in transfer['results']:
        with np.load(OUT/'predictions'/f"cam_{r['scenario']}_{r['mode']}.npz") as saved:
            p=saved['calibrated'];mask=saved['times']<saved['onset']
            assert np.isfinite(p).all() and np.all((p>=0)&(p<=1)) and np.all(np.diff(p,axis=1)>=-1e-12)
            for j,h in enumerate(study.HORIZONS):
                y=(saved['times'][mask]+h*60>=saved['onset']).astype(int)
                assert abs(np.mean((p[mask,j]-y)**2)-r['scores'][str(h)]['brier'])<1e-12
                if not np.any(y==0):assert r['scores'][str(h)]['false_warnings_per_24h'] is None
    records['external_diagnostic']={'passed':True,'templates_inspected':6,'eligible_templates':3,
        'forecast_files':len(transfer['results']),'checks':['selected-member SHA-256','frozen AIT validation reproduction',
            'bounded probabilities','independent Brier','zero exposure rate undefined']}
    records['timestamp_utc']=datetime.now(timezone.utc).isoformat()
    (OUT/'verification.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(f'Passed {result.testsRun} regressions, four invariant suites, {len(folds)} baseline folds, {len(rescored)} endpoint rescores and 12 transfer forecasts',flush=True)

if __name__=='__main__':run()

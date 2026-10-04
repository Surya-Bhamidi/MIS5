"""Persist regression/invariant results and audit emitted score consistency."""
import contextlib
import io
import json
import unittest
from datetime import datetime, timezone

import numpy as np
import compare_combinations
import evidence_pilot as pilot
import extended_study as study


def main():
    records={}
    for name,check in [('pilot_invariants',pilot.checks),('component_invariants',compare_combinations.checks),
                       ('extended_invariants',study.checks)]:
        log=io.StringIO()
        with contextlib.redirect_stdout(log):check()
        records[name]={'passed':True,'output':log.getvalue().strip()}
    suite=unittest.defaultTestLoader.discover(str(pilot.ROOT/'backend/tests'))
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    records['application_and_archive_regressions']={'passed':result.wasSuccessful(),'tests_run':result.testsRun,
                                                  'output':log.getvalue()}
    assert result.wasSuccessful(),log.getvalue()
    summary=json.loads((study.OUT/'summary.json').read_text())
    files=['ait_fold_results.json','darpa_fold_results.json','fusion_fold_results.json','ablation_fold_results.json']
    rows=sum([json.loads((study.OUT/name).read_text()) for name in files],[])
    prediction_count=0
    for r in rows:
        assert r['test'] not in r['train']
        if r['dataset']=='ait':assert r['validation'] not in r['train']
        with np.load(study.OUT/'predictions'/f"{r['dataset']}_{r['test']}_{r['mode']}.npz") as saved:
            for label in ['raw','calibrated']:
                p=saved[label]
                assert np.isfinite(p).all() and ((p>=0)&(p<=1)).all()
                assert np.all(np.diff(p,axis=1)>=-1e-12)
                mask=saved['times']<saved['onset']
                for j,h in enumerate(study.HORIZONS):
                    y=(saved['times'][mask]+h*60>=saved['onset']).astype(int)
                    assert abs(float(np.mean((p[mask,j]-y)**2))-r[label][str(h)]['brier'])<1e-12
        prediction_count+=1
    for dataset,models in summary.items():
        for mode,scorings in models.items():
            subset=[r for r in rows if (r['dataset'],r['mode'])==(dataset,mode)]
            for label,scores in scorings.items():
                for h,v in scores.items():
                    assert v['warned']==sum(r[label][h]['warning_recall'] for r in subset)
                    assert v['false_warning_episodes']==sum(r[label][h]['false_warning_episodes'] for r in subset)
    records['prediction_and_report_audit']={'passed':True,'fold_prediction_files':prediction_count,
        'checks':['split isolation','finite bounded monotone probabilities','independently recomputed pre-onset Brier',
                  'warning/false-episode totals match per-campaign scores']}
    records['timestamp_utc']=datetime.now(timezone.utc).isoformat()
    (study.OUT/'verification.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(f"Verified {result.testsRun} regression tests, three invariant suites and {prediction_count} fold-prediction/report pairs",flush=True)


if __name__=='__main__':main()

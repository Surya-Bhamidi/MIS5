"""Rebuild all original held-out fold experts locally; never train on test/validation.

Generated pickle packages stay under ignored data/. No input is downloaded and
no actuator is connected. Conformance is checked separately after fitting.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import argparse
import hashlib
import json
import pickle
import time

from threadpoolctl import threadpool_limits
import extended_study as study
import robust_forecasting as robust

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'data/research/stress_models'
OUT=ROOT/'experiments/operational_improvements'


def fit_fold(test):
    with threadpool_limits(limits=1):
        started=time.perf_counter()
        meta=[r for r in json.loads((ROOT/'experiments/current_version/metadata.json').read_text()) if r['test']==test]
        thresholds=json.loads((ROOT/'experiments/current_version/thresholds.json').read_text())
        episodes=study.load('ait');train=meta[0]['train'];val=meta[0]['validation']
        if test in train or val in train:raise ValueError('Invalid fitting split')
        context=robust.prepare_context(episodes,train)
        package=dict(version=1,test=test,train=train,validation=val,experts={},scope='Original held-out research fold; controlled local testing only')
        for row in meta:
            key=row['available']
            _,bundle,_=robust.fit_predict(episodes,train,[test],key.split('+'),context)
            threshold=next(r['threshold'] for r in thresholds if r['test']==test and r['available']==key and r['horizon']==30 and r['budget']==1)
            package['experts'][key]=dict(bundle=bundle,calibrators=row['calibrators']['pooled_fixed_blend'],threshold=threshold)
        content=pickle.dumps(package,protocol=pickle.HIGHEST_PROTOCOL)
        path=DEST/f'{test}.pkl';path.write_bytes(content)
        manifest=dict(test=test,train=train,validation=val,experts=len(package['experts']),
                      sha256=hashlib.sha256(content).hexdigest(),seconds=time.perf_counter()-started)
        path.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return manifest


def run(workers):
    DEST.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    names=list(study.load('ait'));results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(fit_fold,name):name for name in names}
        for future in as_completed(futures):
            record=future.result();results.append(record)
            print(f"Fitted {record['test']}: {record['experts']} experts in {record['seconds']:.1f}s",flush=True)
    (OUT/'stress_model_fitting.json').write_text(json.dumps(sorted(results,key=lambda r:r['test']),indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if not 1<=args.workers<=4:parser.error('Use one to four local fitting workers')
    run(args.workers)

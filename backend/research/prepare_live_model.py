"""Rebuild one original six-campaign fold into a local, trusted model package."""
from pathlib import Path
import argparse
import hashlib
import json
import pickle
import time

import numpy as np
from threadpoolctl import threadpool_limits
import extended_study as study
import robust_forecasting as robust
import selective_fusion as selective
from streaming_forecast import ExpertStream

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT/'data/research/live/model.pkl'


def run(test='fox',destination=DEFAULT):
    metadata = [r for r in json.loads((ROOT/'experiments/current_version/metadata.json').read_text()) if r['test']==test]
    thresholds = json.loads((ROOT/'experiments/current_version/thresholds.json').read_text())
    episodes = study.load('ait')
    train = metadata[0]['train']
    context = robust.prepare_context(episodes,train)
    package = dict(version=1,test=test,train=train,validation=metadata[0]['validation'],experts={},
                   scope='Original research fold; no independent production validation')
    checks = []
    for row in metadata:
        start = time.perf_counter()
        key = row['available']
        _,bundle,_ = robust.fit_predict(episodes,train,[test],key.split('+'),context)
        calibration = row['calibrators']['pooled_fixed_blend']
        reference = selective.predict_current(bundle,episodes[test],key.split('+'),row['calibrators'])['risk']
        with np.load(ROOT/'experiments/current_version/predictions'/f'ait_{test}_{key}_pooled_fixed_blend.npz') as saved:
            error = float(np.max(np.abs(reference-saved['risk'])))
        if error > 1e-9:raise ValueError(f'Refitted expert differs from frozen fold: {key} {error}')
        stream = ExpertStream(bundle,calibration)
        # Exercise informative attack activity and the full trailing window,
        # rather than checking only quiet opening bins.
        probe = {**episodes[test],'counts':episodes[test]['counts'][-180:],'times':episodes[test]['times'][-180:]}
        expected = selective.predict_current(bundle,probe,key.split('+'),row['calibrators'])['risk']
        live = np.array([stream.step({str(n):float(v) for n,v in zip(probe['names'],values)}) for values in probe['counts']])
        stream_error = float(np.max(np.abs(live-expected)))
        if stream_error > 1e-9:raise ValueError(f'Stream/batch mismatch: {key} {stream_error}')
        threshold = next(r['threshold'] for r in thresholds if r['test']==test and r['available']==key and r['horizon']==30 and r['budget']==1)
        package['experts'][key] = dict(bundle=bundle,calibrators=calibration,threshold=threshold)
        checks.append(dict(available=key,archive_max_error=error,stream_max_error=stream_error,seconds=time.perf_counter()-start))
        print(f'Prepared {key}: archive error {error:.3g}, streaming error {stream_error:.3g}',flush=True)
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    content = pickle.dumps(package,protocol=pickle.HIGHEST_PROTOCOL)
    destination.write_bytes(content)
    manifest = dict(test=test,train=train,validation=package['validation'],sha256=hashlib.sha256(content).hexdigest(),checks=checks,
                    load_policy='Trusted locally generated pickle only; never accept uploaded model files')
    destination.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    report = ROOT/'experiments/operational_improvements/model_verification.json'
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(manifest,indent=2),encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--fold',default='fox')
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    with threadpool_limits(limits=1):run(args.fold,args.output)

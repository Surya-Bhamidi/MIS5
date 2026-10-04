"""Freeze the reviewed current preset without rerunning model development."""
import hashlib
import json
import shutil
from datetime import datetime,timezone

import evidence_pilot as pilot
from run_selective_fusion import OUT as SOURCE

OUT=pilot.ROOT/'experiments/current_version'
MODE='pooled_fixed_blend'


def run():
    verification=json.loads((SOURCE/'verification.json').read_text());assert verification['passed']
    metadata=json.loads((SOURCE/'metadata.json').read_text());assert len(metadata)==56
    summary=[r for r in json.loads((SOURCE/'summary.json').read_text()) if r['mode']==MODE]
    thresholds=[r for r in json.loads((SOURCE/'thresholds.json').read_text()) if r['mode']==MODE]
    assert len(thresholds)==1344
    (OUT/'predictions').mkdir(parents=True,exist_ok=True)
    chosen=[]
    for m in metadata:
        name=f'ait_{m["test"]}_{m["available"]}_{MODE}.npz'
        shutil.copy2(SOURCE/'predictions'/name,OUT/'predictions'/name)
        chosen.append({'test':m['test'],'validation':m['validation'],'train':m['train'],'available':m['available'],
            'forecast_mode':MODE,'weights':[.25]*6,'calibrators':{MODE:m['calibrators'][MODE]},
            'status':'reviewed development preset; previously inspected campaigns'})
    for path in (SOURCE/'predictions').glob(f'cam_*_{MODE}.npz'):
        shutil.copy2(path,OUT/'predictions'/path.name)
    config={'forecast_mode':MODE,'state_branch_weight':.25,'primary_horizon_minutes':30,
        'horizons_minutes':[1,2,5,10,15,30],'alarm_validation_budget_per_24h':1,
        'default_assumed_response':{'damage':20,'effect_scale':.8,'disruption_scale':1},
        'inference_entry_point':'selective_fusion.predict_current',
        'source_report':'experiments/selective_fusion/REPORT.md','selection':'post-result development choice',
        'further_advancements':'deferred by user','no_sensor_policy':'abstain',
        'scope':'research preset; conditional 30-minute finding; not a measured production defense'}
    for name,value in [('config.json',config),('metadata.json',chosen),('summary.json',summary),('thresholds.json',thresholds)]:
        (OUT/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text(
        '# Frozen current research preset\n\n'
        'Use pooled-calibrated fixed .25 state fusion, with 30-minute warning as the primary use case. '
        'All six horizon probabilities use the same blend. BN inference, forward HMM states and the '
        'Decision Network remain substantive. Further model development is deferred.\n\n'
        'The preset was chosen after reviewing existing test results. It is not a newly confirmed '
        'test-selected paper result. See [the current-version specification](../../docs/CURRENT_VERSION.md) '
        'and [all comparisons](../selective_fusion/REPORT.md) for the conditional gains and losses.\n\n'
        'Prediction archives and validation thresholds are copied exactly; metadata contains the fixed '
        'blend calibrators. No fitting or new test campaign occurs during freezing.\n',encoding='utf-8')
    paths=[p for p in OUT.rglob('*') if p.is_file() and p.name!='reproducibility.json']
    paths += [pilot.ROOT/'docs/CURRENT_VERSION.md',pilot.ROOT/'backend/research/selective_fusion.py',
        pilot.ROOT/'backend/research/freeze_current_version.py',
        pilot.ROOT/'backend/research/verify_current_version.py',SOURCE/'verification.json',SOURCE/'assessment.json']
    manifest={'utc':datetime.now(timezone.utc).isoformat(),'source':str(SOURCE.relative_to(pilot.ROOT)),
        'sha256':{str(p.relative_to(pilot.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (OUT/'reproducibility.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Frozen current preset: 56 AIT fold/subset archives, 3 CAM archives, calibrators, thresholds and hashes',flush=True)


if __name__=='__main__':run()

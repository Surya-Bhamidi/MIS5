"""Paired evaluation of fixed operational warning policy on frozen forecasts.

No model fitting or threshold search. The operational policy was engineered
during development on previously inspected campaigns; it was not preregistered.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.models.warning_policy import WarningPolicy, WarningConfig

OUT = ROOT/'experiments/operational_improvements'
CURRENT = ROOT/'experiments/current_version'
FULL = 'aminer+suricata+wazuh'


def metrics(times, onset, horizon, warning, notifications):
    positive = (times<onset) & (times+horizon*60 >= onset)
    timely = times[notifications & positive]
    starts = warning & ~np.r_[False,warning[:-1]]
    timely_episodes = times[starts & positive]
    return dict(timely_notification=int(len(timely)>0),
                notification_lead_minutes=None if not len(timely) else float((onset-timely[0])/60),
                false_notifications=int(np.sum(notifications & ~positive)),
                false_warning_episodes=int(np.sum(starts & ~positive)),
                timely_warning_episode=int(len(timely_episodes)>0),
                episode_lead_minutes=None if not len(timely_episodes) else float((onset-timely_episodes[0])/60),
                negative_warning_minutes=int(np.sum(warning & ~positive)),
                notifications=int(np.sum(notifications)))


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    roots = {r['scenario']:r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text())}
    thresholds = json.loads((CURRENT/'thresholds.json').read_text())
    rows, hashes = [], {}
    for path in (CURRENT/'thresholds.json',ROOT/'experiments/publication_validation/endpoint_evidence.json',
                 Path(__file__),ROOT/'backend/app/models/warning_policy.py'):
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((CURRENT/'predictions').glob('ait_*.npz')):
        name, available = path.stem.removeprefix('ait_').removesuffix('_pooled_fixed_blend').split('_',1)
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path,allow_pickle=False) as archive:
            mask = archive['times'] < roots[name]
            times, risk = archive['times'][mask], archive['risk'][mask]
            horizons = archive['horizons'].tolist()
        for horizon in (15,30):
            threshold = next(r['threshold'] for r in thresholds if r['test']==name and r['available']==available and r['horizon']==horizon and r['budget']==1)
            scores = risk[:,horizons.index(horizon)]
            raw = scores >= threshold
            raw_starts = raw & ~np.r_[False,raw[:-1]]
            policy = WarningPolicy()
            output = [policy.update(float(t),float(p),threshold,available) for t,p in zip(times,scores)]
            flags = np.array([p['warning'] for p in output])
            notifications = np.array([p['notify'] for p in output])
            baseline = metrics(times,roots[name],horizon,raw,raw_starts)
            improved = metrics(times,roots[name],horizon,flags,notifications)
            y = (times+horizon*60 >= roots[name]).astype(int)
            rows.append(dict(campaign=name,available=available,horizon=horizon,threshold=threshold,
                             baseline=baseline,improved=improved,brier=float(np.mean((scores-y)**2))))
    summary = []
    for available in sorted({r['available'] for r in rows}):
        for horizon in (15,30):
            group = [r for r in rows if r['available']==available and r['horizon']==horizon]
            result = dict(available=available,horizon=horizon,campaigns=len(group))
            for mode in ('baseline','improved'):
                result[mode] = {key:sum(r[mode][key] for r in group) for key in ('timely_notification','false_notifications','false_warning_episodes','timely_warning_episode','negative_warning_minutes','notifications')}
                leads = [r[mode]['notification_lead_minutes'] for r in group if r[mode]['notification_lead_minutes'] is not None]
                result[mode]['mean_notification_lead_minutes'] = float(np.mean(leads)) if leads else None
            result['mean_brier_unchanged'] = float(np.mean([r['brier'] for r in group]))
            summary.append(result)
    payload = dict(schema_version=2,policy=asdict(WarningConfig()),scope='Exploratory paired archived forecast evaluation, not a deployed intervention',
                   metric_definitions={'false_notifications':'Outbound notifications before the target horizon',
                       'false_warning_episodes':'Confirmed warning-state episodes starting before the target horizon',
                       'timely_notification':'Campaign has an outbound notification within the target horizon',
                       'timely_warning_episode':'Campaign has a new confirmed warning-state episode within the target horizon'},
                   threshold_source='Unchanged frozen validation thresholds, budget 1',summary=summary,campaigns=rows)
    (OUT/'evaluation.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    (OUT/'inputs.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    print(json.dumps([s for s in summary if s['available']==FULL],indent=2))
    return payload


if __name__ == '__main__':run()

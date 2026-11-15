"""Paired one-fold outage comparison: zero filling versus matched experts.

The healthy full model is held fixed for the naive zero-fill baseline. The
availability-specific expert and calibrator are the original frozen fold.
"""
from pathlib import Path
import hashlib
import json
import pickle

import numpy as np
from threadpoolctl import threadpool_limits
import extended_study as study
import selective_fusion as selective
from evaluate_improvements import metrics

ROOT=Path(__file__).resolve().parents[2]


def run():
    path=ROOT/'data/research/live/model.pkl'
    content=path.read_bytes()
    manifest=json.loads(path.with_suffix('.json').read_text())
    assert hashlib.sha256(content).hexdigest()==manifest['sha256']
    package=pickle.loads(content)
    ep=study.load('ait')[package['test']]
    onset=next(r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text()) if r['scenario']==package['test'])
    mask=ep['times']<onset
    times=ep['times'][mask]
    y=(times+30*60>=onset).astype(int)
    full=package['experts']['aminer+suricata+wazuh']
    rows=[]
    for key,item in package['experts'].items():
        if key=='aminer+suricata+wazuh':continue
        available=key.split('+')
        missing=set(('aminer','suricata','wazuh'))-set(available)
        counts=ep['counts'].copy()
        counts[:,[str(n).split(':')[0] in missing for n in ep['names']]]=0
        naive=selective.predict_current(full['bundle'],{**ep,'counts':counts},['aminer','suricata','wazuh'],{'pooled_fixed_blend':full['calibrators']})['risk'][mask,-1]
        actual=selective.predict_current(item['bundle'],ep,available,{'pooled_fixed_blend':item['calibrators']})['risk'][mask,-1]
        row=dict(available=key,missing=sorted(missing))
        for mode,risk,threshold in [('zero_fill',naive,full['threshold']),('availability_expert',actual,item['threshold'])]:
            warning=risk>=threshold
            starts=warning & ~np.r_[False,warning[:-1]]
            row[mode]={**metrics(times,onset,30,warning,starts),'brier':float(np.mean((risk-y)**2))}
        row['brier_reduction_percent']=100*(1-row['availability_expert']['brier']/row['zero_fill']['brier'])
        rows.append(row)
    report=dict(campaign=package['test'],scope='One held-out research fold, whole-campaign induced outages, threshold-only warnings; not independent data or a dynamic-outage accuracy study',
                horizon=30,rows=rows)
    destination=ROOT/'experiments/operational_improvements/sensor_outages.json'
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):run()

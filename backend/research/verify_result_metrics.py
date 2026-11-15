"""Independent arithmetic audit of retained selective and published score tables."""
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
import hashlib
import json

import numpy as np
import extended_study as study

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'
FULL='aminer+suricata+wazuh'


def average_precision(target,score):
    positives=int(target.sum())
    if not positives:return 0.
    order=np.argsort(-score,kind='stable');ordered=score[order];labels=target[order]
    ends=np.r_[np.flatnonzero(np.diff(ordered)!=0),len(ordered)-1]
    cumulative=np.cumsum(labels)[ends]
    gains=np.diff(np.r_[0,cumulative])
    return float(np.sum(gains/positives*cumulative/(ends+1)))


def equal(actual,expected,identity):
    if actual is None or expected is None:
        if actual is not expected:raise AssertionError((identity,actual,expected))
    elif not np.isclose(actual,expected,rtol=0,atol=1e-11):raise AssertionError((identity,actual,expected))


def run():
    # Snapshot score tables and metadata before any reads. Refuse a mixed run.
    input_paths=[p for directory in ('selective_fusion','published_comparison','current_version','extended_study','publication_validation')
                 for p in (ROOT/'experiments'/directory).glob('*.json')]
    input_paths += list(study.DATA.glob('ait_*_v2.npz'))
    input_paths += [Path(__file__),ROOT/'backend/research/extended_study.py',ROOT/'backend/research/evidence_pilot.py']
    input_files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    episodes=study.load('ait')
    roots={r['scenario']:r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text())}
    source_files={};prediction_paths={}
    for directory,files in [(ROOT/'experiments/extended_study',['ait_fold_results.json','fusion_fold_results.json','ablation_fold_results.json']),
                            (ROOT/'experiments/publication_validation',['published_hmm_fold_results.json','gru_fold_results.json']),
                            (ROOT/'experiments/published_comparison',['gru_fold_results.json'])]:
        for filename in files:
            for fold in json.loads((directory/filename).read_text()):
                prediction_paths[(fold['mode'],fold['test'])]=directory/'predictions'/f"ait_{fold['test']}_{fold['mode']}.npz"

    @lru_cache(maxsize=48)
    def archive(mode,campaign,available):
        path=(ROOT/'experiments/selective_fusion/predictions'/f'ait_{campaign}_{available}_{mode}.npz'
              if mode.startswith(('pooled_','raw_')) else prediction_paths[(mode,campaign)])
        source_files[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path,allow_pickle=False) as data:
            probabilities=data['risk'].copy() if 'risk' in data else data['calibrated'].copy()
            assert len(probabilities)==len(episodes[campaign]['times'])
            return probabilities

    @lru_cache(maxsize=8)
    def validation_archive(mode,test,available):
        path=ROOT/'experiments/selective_fusion/predictions'/f'ait_{test}_{available}_{mode}.npz'
        with np.load(path,allow_pickle=False) as data:return data['validation_risk'].copy()

    @lru_cache(maxsize=64)
    def threshold_candidates(mode,test,validation,available,horizon):
        onset=episodes[validation]['onset'];mask=episodes[validation]['times']<onset
        times=episodes[validation]['times'][mask]
        scores=validation_archive(mode,test,available)[mask,study.HORIZONS.index(horizon)]
        target=(times+horizon*60>=onset)
        candidates=np.unique(np.r_[0,np.quantile(scores,np.linspace(0,1,257)),scores[target],np.nextafter(scores[target],np.inf),1.000001])
        high=scores[:,None]>=candidates[None,:]
        starts=high&~np.vstack([np.zeros((1,len(candidates)),dtype=bool),high[:-1]])
        timely=starts&target[:,None];warned=timely.any(axis=0);first=np.argmax(timely,axis=0)
        lead=np.where(warned,(onset-times[first])/60,0)
        false=np.sum(starts&~target[:,None],axis=0);minutes=np.sum(high&~target[:,None],axis=0)
        hours=np.sum(~target)/60
        return candidates,warned,lead,false,minutes,false/hours*24

    @lru_cache(maxsize=512)
    def probabilities(mode,campaign,available,horizon,endpoint,delay):
        p=archive(mode,campaign,available)[:,study.HORIZONS.index(horizon)]
        if delay:p=np.r_[np.zeros(delay),p[:-delay]]
        onset=roots[campaign] if endpoint=='successful_root' else episodes[campaign]['onset']
        mask=episodes[campaign]['times']<onset;times=episodes[campaign]['times'][mask];p=p[mask]
        target=(times+horizon*60>=onset).astype(int)
        return times,p,target,float(onset),float(np.mean((p-target)**2)),average_precision(target,p)

    def check_row(row):
        available=row.get('available',FULL);delay=row.get('delay_minutes',0)
        times,p,target,onset,brier,ap=probabilities(row['mode'],row['scenario'],available,row['horizon'],row['endpoint'],delay)
        high=p>=row['threshold'];starts=np.flatnonzero(high&~np.r_[False,high[:-1]])
        positives=np.flatnonzero(high&(target==1));timely=starts[target[starts]==1]
        false=int(np.sum(target[starts]==0));hours=float(np.sum(target==0)/60)
        expected=dict(brier=brier,average_precision=ap,warning_recall=int(bool(len(positives))),
                      lead_minutes=None if not len(positives) else float((onset-times[positives[0]])/60),
                      strict_warning_recall=int(bool(len(timely))),strict_lead_minutes=None if not len(timely) else float((onset-times[timely[0]])/60),
                      false_warning_episodes=false,negative_warning_minutes=float(np.sum(high&(target==0))),
                      negative_exposure_hours=hours,false_warnings_per_24h=None if not hours else false/hours*24)
        for key,value in expected.items():
            if key in row:equal(row[key],value,(row['mode'],row['scenario'],row['horizon'],row['endpoint'],key))

    tables={
        'selective':json.loads((ROOT/'experiments/selective_fusion/scored.json').read_text()),
        'published_budgets':json.loads((ROOT/'experiments/published_comparison/budget_fold_results.json').read_text()),
        'published_original':json.loads((ROOT/'experiments/published_comparison/original_threshold_scores.json').read_text()),
    }
    for name,rows in tables.items():
        for row in rows:check_row(row)
        print(f'Independently checked {name}: {len(rows)} score rows',flush=True)
    thresholds=json.loads((ROOT/'experiments/selective_fusion/thresholds.json').read_text())
    for row in thresholds:
        candidates,warned,lead,false,minutes,rates=threshold_candidates(row['mode'],row['test'],row['validation'],row['available'],row['horizon'])
        eligible=np.flatnonzero((rates<=row['budget']+1e-12)&(minutes<=5))
        best=max(eligible,key=lambda i:(int(warned[i]),float(lead[i]),-int(minutes[i]),-int(false[i]),float(candidates[i])))
        equal(row['threshold'],float(candidates[best]),('validation optimum',row['test'],row['mode'],row['horizon']))
        index=int(np.flatnonzero(candidates==row['threshold'])[0]);saved=row['validation_metrics']
        equal(saved['strict_warning_recall'],int(warned[index]),'validation coverage')
        equal(saved['strict_lead_minutes'],float(lead[index]) if warned[index] else None,'validation lead')
        equal(saved['false_warning_episodes'],int(false[index]),'validation false episodes')
        equal(saved['negative_warning_minutes'],float(minutes[index]),'validation warning minutes')
    print(f'Independently checked {len(thresholds)} validation threshold selections and their constrained optima',flush=True)
    aggregate_checks=0
    for filename,rows,keys in [
        ('experiments/selective_fusion/summary.json',tables['selective'],('mode','available','endpoint','horizon','budget','delay_minutes')),
        ('experiments/current_version/summary.json',[r for r in tables['selective'] if r['mode']=='pooled_fixed_blend'],('mode','available','endpoint','horizon','budget','delay_minutes')),
        ('experiments/published_comparison/budget_summary.json',tables['published_budgets'],('mode','endpoint','horizon','budget')),
        ('experiments/published_comparison/original_threshold_summary.json',tables['published_original'],('mode','endpoint','horizon'))]:
        groups=defaultdict(list)
        for row in rows:groups[tuple(row[k] for k in keys)].append(row)
        for summary in json.loads((ROOT/filename).read_text()):
            group=groups[tuple(summary[k] for k in keys)];leads=[r['strict_lead_minutes'] for r in group if r['strict_lead_minutes'] is not None]
            expected=dict(campaigns=len(group),mean_brier=float(np.mean([r['brier'] for r in group])),
                          mean_ap=float(np.mean([r['average_precision'] for r in group])),warned=sum(r['warning_recall'] for r in group),
                          strict_warned=sum(r['strict_warning_recall'] for r in group),false_episodes=sum(r['false_warning_episodes'] for r in group),
                          negative_warning_minutes=sum(r['negative_warning_minutes'] for r in group),
                          median_strict_lead=None if not leads else float(np.median(leads)))
            assert len(group)==8
            for key,value in expected.items():equal(summary[key],value,(filename,tuple(summary[k] for k in keys),key))
            aggregate_checks+=1
    for relative,digest in {**input_files,**source_files}.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,('Input changed during verification',relative)
    output=dict(passed=True,input_sha256=input_files,score_rows={name:len(rows) for name,rows in tables.items()},
                total_score_rows=sum(len(rows) for rows in tables.values()),aggregate_rows=aggregate_checks,
                average_precision_independently_ranked=True,prediction_archives_checked=len(source_files),
                validation_thresholds_checked=len(thresholds),validation_grid_optima_verified=True,
                archive_sha256=source_files,scope='Retained scores and aggregate arithmetic; not new independent model performance evidence')
    (OUT/'metrics_verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k not in ('archive_sha256','input_sha256')},indent=2))


if __name__=='__main__':
    if not __debug__:raise RuntimeError('Run verification without Python optimization')
    run()

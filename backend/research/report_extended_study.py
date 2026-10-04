"""Build complete tables, descriptive paired uncertainty and paper figures."""
import csv
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import extended_study as study
import evidence_pilot as pilot

LABELS={'static_bn':'Static BN','detector_hmm':'Detector BN-HMM',
    'duration_hmm':'Duration BN-HMM','temporal_logistic':'Temporal logistic',
    'temporal_boosting':'Boosted-tree forecast','equal_fusion':'Equal fusion',
    'conditional_fusion':'Learned conditional fusion'}
MAIN_MODES=list(LABELS)
ABLATIONS={'boosting_current_only':'Tree: current counts only',
    'boosting_only_aminer':'Tree: AMiner only',
    'boosting_only_suricata':'Tree: Suricata only',
    'boosting_only_wazuh':'Tree: Wazuh only'}
LABELS.update(ABLATIONS)


def read(name):
    return json.loads((study.OUT/name).read_text(encoding='utf-8'))


def csv_write(name,rows):
    with (study.OUT/name).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def aggregate(rows,label,h):
    values=[r[label][str(h)] for r in rows]
    leads=[v['lead_minutes'] for v in values if v['lead_minutes'] is not None]
    exposure=sum(v['negative_exposure_hours'] for v in values)
    false=sum(v['false_warning_episodes'] for v in values)
    return dict(episodes=len(values),mean_brier=float(np.mean([v['brier'] for v in values])),
        mean_average_precision=float(np.mean([v['average_precision'] for v in values])),
        warned=sum(v['warning_recall'] for v in values),false_warning_episodes=false,
        negative_warning_minutes=sum(v['negative_warning_minutes'] for v in values),
        negative_exposure_hours=exposure,false_warnings_per_24h=false/exposure*24,
        median_lead_when_warned=None if not leads else float(np.median(leads)),
        lead_including_misses=float(np.mean([v['lead_minutes'] or 0 for v in values])),
        campaigns_over_false_rate_budget=sum(v['false_warnings_per_24h']>1 for v in values),
        campaigns_over_negative_minutes_budget=sum(v['negative_warning_minutes']>5 for v in values))


def paired(rows,candidate,baseline):
    index={(r['test'],r['mode']):r for r in rows}
    names=sorted(r['test'] for r in rows if r['mode']==candidate)
    rng=np.random.default_rng(1729)
    draws=rng.integers(0,len(names),size=(20000,len(names)))
    result={}
    for h in study.HORIZONS:
        result[str(h)]={}
        for metric,sign in [('brier',-1),('average_precision',1),('warning_recall',1),
                            ('false_warning_episodes',-1),('negative_warning_minutes',-1)]:
            delta=np.array([sign*(index[n,candidate]['calibrated'][str(h)][metric]-
                index[n,baseline]['calibrated'][str(h)][metric]) for n in names])
            limits=np.quantile(delta[draws].mean(axis=1),[.025,.975])
            result[str(h)][metric]={'mean_improvement':float(delta.mean()),
                'descriptive_95_percent_bootstrap_interval':limits.tolist(),
                'improved_campaigns':int(np.sum(delta>1e-12)),
                'worse_campaigns':int(np.sum(delta < -1e-12)),
                'campaign_improvements':dict(zip(names,delta.tolist()))}
    return result


def sensitivity(rows):
    results=[]
    episodes={d:study.load(d) for d in ['ait','darpa']}
    for r in rows:
        ep=episodes[r['dataset']][r['test']]
        with np.load(study.OUT/'predictions'/f"{r['dataset']}_{r['test']}_{r['mode']}.npz") as saved:
            p=saved['calibrated'].copy()
        for damage in [10.,20.,50.]:
            for disruption in [.5,1.,2.]:
                for effect in [.5,.8,1.]:
                    aware=study.realized_decision_cost(ep,p,True,damage,effect,disruption)
                    blind=study.realized_decision_cost(ep,p,False,damage,effect,disruption)
                    results.append(dict(dataset=r['dataset'],test=r['test'],mode=r['mode'],
                        damage=damage,disruption_scale=disruption,effect_scale=effect,
                        aware_assumed_cost=aware['mean_assumed_cost'],
                        ignores_delay_assumed_cost=blind['mean_assumed_cost'],
                        improvement=blind['mean_assumed_cost']-aware['mean_assumed_cost']))
    csv_write('decision_sensitivity.csv',results)
    summary={}
    for dataset in ['ait','darpa']:
        summary[dataset]={}
        for mode in sorted(set(r['mode'] for r in results if r['dataset']==dataset)):
            cells=[]
            for damage in [10.,20.,50.]:
                for disruption in [.5,1.,2.]:
                    for effect in [.5,.8,1.]:
                        cell=[r['improvement'] for r in results if (r['dataset'],r['mode'],r['damage'],
                            r['disruption_scale'],r['effect_scale'])==(dataset,mode,damage,disruption,effect)]
                        cells.append(float(np.mean(cell)))
            summary[dataset][mode]={'settings':27,'mean_assumed_improvement':float(np.mean(cells)),
                'improved_settings':sum(v>1e-12 for v in cells),'worse_settings':sum(v < -1e-12 for v in cells),
                'minimum_setting_improvement':min(cells),'maximum_setting_improvement':max(cells)}
    (study.OUT/'decision_sensitivity_summary.json').write_text(json.dumps(summary,indent=2))
    return summary


def plots(rows,summary):
    figures=study.OUT/'figures';figures.mkdir(exist_ok=True)
    modes=MAIN_MODES
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,metric,title in [(axes[0],'mean_brier','Brier error (lower is better)'),
                           (axes[1],'mean_average_precision','Average precision (higher is better)')]:
        for mode in modes:
            ax.plot(study.HORIZONS,[summary['ait'][mode]['calibrated'][str(h)][metric] for h in study.HORIZONS],
                marker='o',label=LABELS[mode])
        ax.set(xlabel='Forecast horizon (minutes)',title=title);ax.grid(alpha=.2)
    axes[1].legend(fontsize=7,loc='upper left')
    fig.suptitle('AIT: eight reused development scenarios; mean of held-out campaign scores')
    fig.savefig(figures/'ait_forecast_metrics.png',dpi=200);fig.savefig(figures/'ait_forecast_metrics.pdf');plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(15,7),layout='constrained')
    for ax,name in zip(axes.flat,pilot.SCENARIOS):
        for mode in ['temporal_boosting','conditional_fusion']:
            with np.load(study.OUT/'predictions'/f'ait_{name}_{mode}.npz') as saved:
                minutes=(saved['times']-saved['onset'])/60
                selected=(minutes>=-60)&(minutes<0)
                ax.plot(minutes[selected],saved['calibrated'][selected,study.HORIZONS.index(15)],label=LABELS[mode])
        ax.axvline(-15,color='gray',linestyle=':');ax.axvline(0,color='black',linestyle='--')
        ax.set(title=name,ylim=(0,1),xlabel='Minutes relative to scheduled onset');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7);fig.suptitle('All AIT scenarios: calibrated 15-minute risk, final pre-onset hour')
    fig.savefig(figures/'ait_all_campaigns.png',dpi=200);fig.savefig(figures/'ait_all_campaigns.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,name in zip(axes,['1.0','2.0.2']):
        for mode in ['detector_hmm','duration_hmm','temporal_boosting']:
            with np.load(study.OUT/'predictions'/f'darpa_{name}_{mode}.npz') as saved:
                minutes=(saved['times']-saved['onset'])/60;selected=minutes<0
                ax.plot(minutes[selected],saved['raw'][selected,study.HORIZONS.index(15)],label=LABELS[mode])
        ax.axvline(-15,color='gray',linestyle=':');ax.axvline(0,color='black',linestyle='--')
        ax.set(title='DARPA '+name,ylim=(0,1),xlabel='Minutes relative to actual ACK flood onset');ax.grid(alpha=.2)
    axes[0].legend(fontsize=8);fig.suptitle('Two DARPA transfer case studies: uncalibrated 15-minute risk')
    fig.savefig(figures/'darpa_transfer.png',dpi=200);fig.savefig(figures/'darpa_transfer.pdf');plt.close(fig)


def table(summary,dataset,h,modes):
    lines=['| Method | Brier ↓ | AP ↑ | Warned | False episodes | False / 24h | Negative warning min | Median lead, warned only |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for mode in modes:
        v=summary[dataset][mode]['calibrated'][str(h)]
        lead='—' if v['median_lead_when_warned'] is None else f"{v['median_lead_when_warned']:.2f} min"
        lines.append(f"| {LABELS[mode]} | {v['mean_brier']:.6f} | {v['mean_average_precision']:.4f} | {v['warned']}/{v['episodes']} | {v['false_warning_episodes']} | {v['false_warnings_per_24h']:.3f} | {v['negative_warning_minutes']:.0f} | {lead} |")
    return '\n'.join(lines)


def main():
    rows=read('ait_fold_results.json')+read('darpa_fold_results.json')+read('fusion_fold_results.json')+read('ablation_fold_results.json')
    expected={'ait':8,'darpa':2}
    summary={};flat=[];fixed=[]
    for dataset in expected:
        summary[dataset]={}
        for mode in LABELS:
            subset=[r for r in rows if r['dataset']==dataset and r['mode']==mode]
            if not subset:continue
            assert len(subset)==expected[dataset] and len({r['test'] for r in subset})==len(subset)
            summary[dataset][mode]={label:{str(h):aggregate(subset,label,h) for h in study.HORIZONS}
                                    for label in ['raw','calibrated']}
            for r in subset:
                for label in ['raw','calibrated']:
                    for h in study.HORIZONS:
                        flat.append(dict(dataset=dataset,test=r['test'],mode=mode,scoring=label,horizon=h,**r[label][str(h)]))
                        for threshold,values in r[label+'_fixed_thresholds'].items():
                            fixed.append(dict(dataset=dataset,test=r['test'],mode=mode,scoring=label,horizon=h,
                                              **values[str(h)]))
    csv_write('all_scores.csv',flat);csv_write('fixed_thresholds.csv',fixed)
    (study.OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    ait=[r for r in rows if r['dataset']=='ait']
    pairs={'fusion_vs_boosting':paired(ait,'conditional_fusion','temporal_boosting'),
           'boosting_vs_detector_hmm':paired(ait,'temporal_boosting','detector_hmm'),
           'boosting_vs_aminer_only':paired(ait,'temporal_boosting','boosting_only_aminer'),
           'boosting_vs_current_only':paired(ait,'temporal_boosting','boosting_current_only'),
           'duration_vs_detector_hmm':paired(ait,'duration_hmm','detector_hmm')}
    (study.OUT/'paired_comparisons.json').write_text(json.dumps(pairs,indent=2))
    decision=sensitivity(rows)
    stress_summary={}
    for dataset in expected:
        stress=read(f'{dataset}_sensor_stress.json');stress_summary[dataset]={}
        for sensor in sorted({r['dropped_sensor'] for r in stress}):
            stress_summary[dataset][sensor]={}
            for mode in summary[dataset]:
                subset=[r for r in stress if r['mode']==mode and r['dropped_sensor']==sensor]
                if mode in ABLATIONS:continue
                assert len(subset)==expected[dataset]
                stress_summary[dataset][sensor][mode]={str(h):aggregate(subset,'calibrated',h) for h in study.HORIZONS}
    (study.OUT/'sensor_stress_summary.json').write_text(json.dumps(stress_summary,indent=2))
    plots(rows,summary)
    lines=['# Extended research results — 4 October 2026','',
        '**Verdict: useful improvements were measured against reproduced component baselines. A universal advantage over the strongest tested baseline, originality of the combination, and superiority to complete published systems are not established.**','',
        'The tested learned combination joins a duration-aware BN-HMM forecast and a boosted-tree forecast using a conditional logistic CPD trained on inner held-out campaigns. This is conventional stacking. Equal averaging is also tested. At 30 minutes learned fusion has the same 5/8 warning coverage as boosting and 5 rather than 20 false-warning episodes; probability error and ranking worsen. Most of the false-episode reduction comes from wheeler (17 to 1), offset by more false episodes on harrison (0 to 2). Equal averaging has only three false episodes at that horizon but worse probability quality and earlier warning coverage is weaker. This is a narrow operating-point result, not general superiority.','',
        'A separate positive combination finding: at 15 minutes the three-sensor temporal tree warns on 5/8 campaigns versus 2/8 for the AMiner-only temporal tree, with three false episodes for each. Mean Brier falls from 0.001576 to 0.001098 (30.3% reduction), and AP rises from 0.6565 to 0.7214. The Wazuh-only tree also warns on 2/8, Suricata-only on 0/8, and the all-sensor current-count-only tree on 0/8. This supports the value of combining sensor histories on this task. At five minutes AMiner-only has better AP and 3/8 coverage than either the full tree or learned fusion; the gain is horizon-dependent. None of these comparisons alone establishes algorithmic originality.','',
        '## Dataset and evaluation','',
        '- AIT: all eight scenarios, rotating six fitting / one validation / one test. The target is the published scheduled privilege-escalation start, not verified compromise or DDoS. Current detector identifiers and trailing 5/15/60-minute counts are the only supervised inputs; no target labels, host identities or relative-onset time are features. AIT was inspected and evaluated in preceding pilots: this extension is exploratory reused development evidence.',
        '- DARPA: both local tar.gz archives, full inside and DMZ PCAPs, background included; 1,628,616 packets in total. Target is the first ACK flood burst, not the phase-5 login. March uses EST and April EDT. Only two related campaigns; transfer thresholds use the fitting campaign, not independent validation. MIT states the DDoS did not actually succeed, so flood emission is the endpoint.',
        '- A forecast at minute t uses only completed bins ending by t. Observed alert timestamp availability is assumed; actual end-to-end collection latency is not validated. Exact report identities are deduplicated. Vocabulary, bucket edges, emission/transition/duration parameters and supervised models use fitting campaigns only. Fusion coefficients use two inner three-versus-three campaign splits. Calibration and warning thresholds use the outer validation campaign.',
        '- AIT retains the earlier pilot clock beginning at midnight before the earliest alert. Initial empty prefixes total about 4.5 hours across the eight scenarios; they are included in approximately 790 hours of negative clock exposure. Continuous telemetry coverage cannot be verified from alert-only data. Rates assume coverage on that grid, and must not be described as independently verified benign operating hours.',
        '- Every model shares labels, clock and evaluation exposure. Warning selection constrains validation to at most one false episode per 24 negative hours and five negative warning minutes. Those limits are not guaranteed on test campaigns. An episode is false if its start lies outside the target horizon; continuous false warnings that persist into that horizon can also count toward warning coverage. Negative warning minutes reveal persistent alarms. AP is sklearn average precision, not trapezoidal PR area.',
        '- Scores are campaign means, not pooled independent alert samples. Every horizon, raw and calibrated score, fixed threshold and negative result is released. Transformed sensor-outage traces are not additional independent campaigns.','',
        '## AIT natural traces: 15-minute forecasts','',table(summary,'ait',15,MAIN_MODES),'',
        '## AIT natural traces: 5-minute forecasts','',table(summary,'ait',5,MAIN_MODES),'',
        '## AIT natural traces: 30-minute forecasts','',table(summary,'ait',30,MAIN_MODES),'',
        '## Fixed-setting feature ablations: 15-minute forecasts','',
        'Each single-sensor tree is trained on that sensor, unlike removal stress. The current-count tree omits all temporal means. These additional comparisons were declared after the initial results and remain exploratory; they do not tune or replace the candidate. All six horizons are preserved in the summary and CSV files.','',
        table(summary,'ait',15,list(ABLATIONS)+['temporal_boosting']),'',
        '## Paired uncertainty for fusion versus boosting','',
        'Campaign bootstrap (20,000 draws, seed 1729). Positive differences favor fusion. Intervals are descriptive: only eight related scenarios, overlapping fitted models, reused test results and multiple exploratory comparisons prevent confirmatory significance claims.','',
        '| Horizon | Brier improvement [95% descriptive interval] | AP improvement [interval] | False episodes reduced per campaign [interval] |',
        '|---|---:|---:|---:|']
    for h in [5,15,30]:
        cells=[]
        for metric in ['brier','average_precision','false_warning_episodes']:
            v=pairs['fusion_vs_boosting'][str(h)][metric];lo,hi=v['descriptive_95_percent_bootstrap_interval']
            cells.append(f"{v['mean_improvement']:.6g} [{lo:.6g}, {hi:.6g}]")
        lines.append('| '+str(h)+' min | '+' | '.join(cells)+' |')
    lines+=['','## DARPA transfer: 15-minute forecasts','',table(summary,'darpa',15,study.MODES),'',
        'The duration model improves the two-campaign mean Brier over the ordinary detector HMM, but only one of two outcomes is warned and six false episodes occur. One transfer improves and the other worsens. Very short negative exposure amplifies false-warning rates; this is not a validated operational DDoS system. Phase labels also represent different intermediate behaviors between the two DARPA variants.','',
        '## Equal-input sensor-outage stress','',
        'Each sensor is removed for the entire held-out trace. Training, calibration, thresholds and ground truth remain natural and unchanged. Missing telemetry is represented by zero counts without an explicit health flag; this measures robustness to that particular input failure.','',
        '| Removed AIT sensor | Method | 15-min Brier | AP | Warned | False episodes |',
        '|---|---|---:|---:|---:|---:|']
    for sensor,methods in stress_summary['ait'].items():
        for mode in ['duration_hmm','temporal_boosting','conditional_fusion']:
            v=methods[mode]['15']
            lines.append(f"| {sensor} | {LABELS[mode]} | {v['mean_brier']:.6f} | {v['mean_average_precision']:.4f} | {v['warned']}/8 | {v['false_warning_episodes']} |")
    lines+=['','With Suricata removed, fusion warns on 5/8 versus 3/8 campaigns for boosting and gives two versus four false episodes, but probability error and ranking are worse. With AMiner or Wazuh removed, neither issues a successful 15-minute warning. This is a specific coverage/false-alarm tradeoff, not robustness to all sensor failures. Complete stress results for every main method, both datasets and all horizons are in sensor_stress_summary.json and the per-campaign JSON files.','',
        '## Response-delay Decision Network sensitivity','',
        'The chance node is first-onset time; the decision node is Monitor/Restrict/Block/Isolate; an action-effect table and disruption/damage costs give expected loss. Compare delay-aware action selection with the same forecast ignoring delay. Both realized cost proxies respect actual assumed action delay. Evaluate all 27 combinations of damage 10/20/50, disruption scale .5/1/2 and assumed efficacy scale .5/.8/1.','',
        '| Dataset / forecast | Improved settings | Worse settings | Mean modeled cost reduction | Range across settings |',
        '|---|---:|---:|---:|---:|']
    for dataset,modes in decision.items():
        for mode in modes:
            v=modes[mode]
            lines.append(f"| {dataset} / {LABELS[mode]} | {v['improved_settings']}/27 | {v['worse_settings']}/27 | {v['mean_assumed_improvement']:.6g} | [{v['minimum_setting_improvement']:.6g}, {v['maximum_setting_improvement']:.6g}] |")
    lines+=['','These are framewise assumed costs on passive logs. Actions were not executed; costs, delays and efficacy are not measured. Repeated per-minute actions are not a sequential response simulator. No measured prevention claim follows.','',
        '## Novelty and comparison with publications','',
        'HMM multistep prediction already appears in [Holgado et al., institutional record](https://portalcientifico.upm.es/en/ipublic/item/5643464) and [Dass et al., original paper](https://arxiv.org/abs/2106.02012). Explicit-duration HSMMs have prior cyber anomaly-detection work: [Tan and Xi, publisher abstract](https://www.sciencedirect.com/science/article/pii/S0096300308003342), DOI 10.1016/j.amc.2008.05.028. The indexed publisher abstract and introduction describe HSMM intrusion anomaly detection; full text was not accessible during the final check. [Cross-validated stacking](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html) is an established ensemble method. The combination is not a newly invented inference principle.','',
        'Our static BN, categorical HMM, expanded duration HMM, logistic and boosted-tree methods reproduce standard components with explicit settings; they do not reproduce complete named published systems. Their endpoints, observation mappings and metrics often differ. No published accuracy/F1 has been compared directly to our scores. Closest full-system reproductions and original held-out campaigns remain needed before claiming superiority to existing work. See ../../docs/NOVELTY_AUDIT.md.','',
        '## Defensible paper direction','',
        '**Working title:** Forecasting Cyberattack Onset from Multi-Sensor Alerts: Duration Models, Learned Fusion and Warning–Calibration Tradeoffs.','',
        'The candidate contribution is a reproducible empirical study of when learned fusion changes prospective warning behavior, with a separate packet-based DDoS transfer case study and explicit response assumptions. It includes substantive BN inference (Unit 1), an HMM with phase-duration expansion (Unit 2), and a Decision Network (Unit 3). The boosted tree is an additional forecast source and a mandatory strong baseline.','',
        'A supported preliminary claim: “On eight reused AIT scenarios, under a common validation warning rule, learned fusion maintained 5/8 30-minute episode warning coverage while reducing false-warning episodes from 20 to 5 relative to the boosted-tree forecaster, at the cost of worse Brier error and ranking. The reduction was concentrated in one scenario.”','',
        'Before a superiority or novelty paper submission: freeze this model and protocol; verify target execution times and telemetry availability from independent attacker/receipt logs; obtain fresh independent campaigns including benign-only and aborted attacks; reproduce the closest published prediction systems on this same endpoint; validate actual response delays/effects if response benefits are claimed. No further tuning on these eight traces can replace that fresh test. An empirical/benchmark paper may still be viable, depending on venue and stronger endpoint validation.','',
        '## Artifacts and verification','',
        '- summary.json, all_scores.csv: all six horizons, natural raw/calibrated scores and warning counts.',
        '- fixed_thresholds.csv: .01/.05/.1/.5 operating points for every campaign and horizon.',
        '- paired_comparisons.json: full signed campaign differences and descriptive intervals.',
        '- decision_sensitivity.csv and decision_sensitivity_summary.json: all assumed cost/effect settings.',
        '- predictions/: every fitted-fold validation/test probability array; *_metadata.json: vocabularies, bucket edges, durations and fusion coefficients.',
        '- figures/: standalone PNG/PDF metric, all-campaign and DARPA forecast plots.',
        '- reproducibility.json: source/config/cache/archive SHA-256 hashes and package versions.',
        '- verification.json: thirteen regression tests, three research invariant suites and independent consistency checks for all 98 saved fold-prediction/report pairs.',
        '- Application ingestion regressions cover label invariance and future-data independence. Research checks cover causal prefixes, replay invariance, probability coherence, duration transitions and delayed utility. Sensor stress refits reproduce saved natural supervised predictions to numerical tolerance.',
        '- The research engine is separate from the legacy dashboard. Ingestion was corrected, but cached application tables, legacy XML local-time conversion and the dashboard’s hand-coded address boosts/event-count progression are not this validated forecasting method. Do not use dashboard accuracy as the research result.','',
        'Reproduce from project root with backend/research/run_extended_study.ps1. Data preparation reads archives in place; rerunning deterministically replaces only this study’s generated outputs. Earlier pilot reports remain intact.']
    (study.OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    paths=list(Path(__file__).parent.glob('*.py'))+list((pilot.ROOT/'experiments').glob('*protocol.md'))
    paths+=list(Path(__file__).parent.glob('*.ps1'))+list(Path(__file__).parent.glob('requirements*.txt'))
    paths+=[pilot.ROOT/'backend/app/ingestion/normalizer.py']+list((pilot.ROOT/'backend/tests').glob('test*.py'))
    paths+=list(study.DATA.glob('*.npz'))
    paths+=[pilot.ROOT/'LLS_DDOS_1.0.tar.gz',pilot.ROOT/'LLS_DDOS_2.0.2.tar.gz',pilot.DATA/'ait_ads.zip',pilot.DATA/'labels.csv']
    hashes={}
    for path in paths:
        with path.open('rb') as stream:hashes[str(path.relative_to(pilot.ROOT))]=hashlib.file_digest(stream,'sha256').hexdigest()
    versions={p:importlib.metadata.version(p) for p in ['numpy','scipy','scikit-learn','matplotlib']}
    (study.OUT/'reproducibility.json').write_text(json.dumps({'python':platform.python_version(),'packages':versions,
        'seed':1729,'bootstrap_draws':20000,'horizons_minutes':study.HORIZONS,'source_and_input_sha256':hashes,
        'validation_threshold_budget':{'false_episodes_per_24_negative_hours':1,'negative_warning_minutes':5},
        'evaluation_status':'exploratory; reused AIT development scenarios; two DARPA transfer cases'},indent=2))
    print('Wrote complete extended study report, CSV/JSON tables, hashes and six PNG/PDF figures',flush=True)


if __name__=='__main__':
    main()

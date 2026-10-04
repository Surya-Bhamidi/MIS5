"""Generate supplemental tables/figures from saved, unmodified experiment outputs."""
import csv
import hashlib
import json
import platform
from datetime import datetime,timezone
import importlib.metadata

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import evidence_pilot as pilot
import extended_study as study
from audit_endpoints import OUT

def run():
    endpoint=json.loads((OUT/'endpoint_summary.json').read_text())
    per_campaign=json.loads((OUT/'endpoint_rescored.json').read_text())
    evidence=json.loads((OUT/'endpoint_evidence.json').read_text())
    new_folds=json.loads((OUT/'published_hmm_fold_results.json').read_text())+json.loads((OUT/'gru_fold_results.json').read_text())
    original=json.loads((study.OUT/'ait_fold_results.json').read_text())+json.loads((study.OUT/'fusion_fold_results.json').read_text())+json.loads((study.OUT/'ablation_fold_results.json').read_text())
    all_folds=original+new_folds
    rows=[]
    for mode in sorted({r['mode'] for r in all_folds}):
        selected=[r for r in all_folds if r['mode']==mode]
        for label in ['raw','calibrated']:
            for horizon in study.HORIZONS:
                scores=[r[label][str(horizon)] for r in selected]
                strict=[r for r in per_campaign if r['mode']==mode and r['endpoint']=='scheduled_onset'
                        and r['horizon']==horizon and r['delay_minutes']==0]
                rows.append({'mode':mode,'scoring':label,'horizon':horizon,'campaigns':len(selected),
                    'mean_brier':float(np.mean([s['brier'] for s in scores])),
                    'mean_ap':float(np.mean([s['average_precision'] for s in scores])),
                    'warned':sum(s['warning_recall'] for s in scores),
                    'strict_warned':sum(s['strict_warning_recall'] for s in scores) if mode.startswith(('perera','ansari'))
                        else (sum(s['strict_warning_recall'] for s in strict) if label=='calibrated' else None),
                    'false_episodes':sum(s['false_warning_episodes'] for s in scores),
                    'negative_warning_minutes':sum(s['negative_warning_minutes'] for s in scores)})
    with (OUT/'baseline_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'baseline_summary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    selected=[r for r in rows if r['scoring']=='calibrated' and r['horizon']==15]
    text=['# Publication validation report','',
        '**Current research version:** fixed .25 BN/HMM state fusion, with 30-minute warning as its primary use case. Further advancements are deferred. See [the preset specification](../../docs/CURRENT_VERSION.md) and [frozen artifacts](../current_version/README.md). This post-result development choice preserves every earlier comparison and does not establish a universally best model.','',
        '**Latest completed analysis:** [selective fusion with campaign-based calibration](../selective_fusion/REPORT.md) has passed 33 tests and independent score/selection checks. A prespecified .25 state blend gives 5/8 timely 30-minute root warnings versus 4/8 for original counts-only, 4.25% lower Brier and five versus 19 false episodes overall. The false-episode gain reverses when wheeler is removed. The adaptive selector produces 5/8 15-minute warnings but 17 false episodes, so its primary target fails. Missing-Wazuh selective fusion has a conditional gain against matched pooled counts. No overall superiority or independent generalization is established.','',
        '**Previous improvement analysis:** [revised availability and BN/HMM experiments](../robust_forecasting/REPORT.md) tested state features and confirmation. Availability-specific counts recovered 3/8 timely warnings with Wazuh missing, but full-input state augmentation worsened 15-minute coverage and probability error. The confirmation revision selected no HMM confirmation at the primary horizons. The frozen original results below remain unchanged.','',
        'This extends the completed exploratory study. It makes the evidence more auditable; it does not establish first-ever architecture, state of the art, or guaranteed publication. Existing predictions and thresholds were frozen for endpoint and latency rescoring. All negative results are retained.','',
        'Additional completed checks are in [the comparison report](../published_comparison/REPORT.md): eight validation-selected longer GRU folds, a pinned author-code audit and four validation-selected alarm policies across 15 model variants. At a tighter 30-minute budget, boosting gives 4/8 timely root warnings versus 3/8 for fusion at two false episodes each; at the larger budget both give 4/8 and fusion reduces false episodes from 19 to 4. This strengthens the evidence for a policy-dependent tradeoff, not full published-system superiority.','',
        '## Successful endpoint validation','',
        'Original attacker execution logs and attack-labelled victim audit records were retrieved for every AIT campaign. SHA-256 validates the local selected members, and ZIP CRC checks ran during retrieval. Only selected ZIP members were downloaded; whole archive checksums were not verified. Evaluation labels never enter count features.','',
        '| Campaign | Successful user-change offset (s) | Successful root offset (s) |',
        '|---|---:|---:|']
    text += [f"| {r['scenario']} | {r['change_user_offset_seconds']:.3f} | {r['root_offset_seconds']:.3f} |" for r in evidence]
    text += ['',
        'Offsets are relative to the published scheduled escalation. A successful USER_START session for `/bin/su` confirms the change from web-service identity to a system user. A later attack-labelled `/usr/bin/sudo` USER_START session with account root is the distinct root endpoint. The root rescore retains models trained for the original scheduled endpoint; it is an endpoint sensitivity analysis, not a newly fitted root predictor.','',
        'The earlier DNSteal ordering concern is resolved by the original dataset paper: exfiltration deliberately starts at simulation beginning as a separate background attack. Negative forecast exposure therefore means no impending target event, not necessarily benign traffic.','',
        '## Same-task baseline results at 15 minutes','',
        'Each AIT fold has six fitting, one calibration/threshold and one test campaign. Scores are campaign means, not millions of independent attacks. Lower Brier is better; higher average precision is better. Timely new warnings require a warning episode to BEGIN inside the valid forecast window. Any-warning coverage also counts persistent earlier alerts and is therefore more permissive.','',
        '| Model | Mean Brier | Mean AP | Any warning / 8 | Timely new warning / 8 | False episodes |',
        '|---|---:|---:|---:|---:|---:|']
    text += [f"| {r['mode']} | {r['mean_brier']:.7f} | {r['mean_ap']:.4f} | {r['warned']} | {r['strict_warned']} | {r['false_episodes']} |" for r in selected]
    text += ['',
        'The Perera2016 adaptation uses fitted count clusters, an unsupervised categorical HMM and an added target hazard. The paper instead predicts next alert clusters from per-alert bag-of-words/IP/port features. The GRU is a bounded implementation inspired by Ansari2022; it predicts first onset from minute counts instead of Warden next alerts. These are comparable implementations of adapted method families, not full published-system reproductions. Original accuracy figures must not be compared with these Brier scores.','',
        '## Observed root endpoint: operational tradeoff at 30 minutes','',
        '| Model | Mean Brier | Mean AP | Any / new warnings | False episodes | Median new-warning lead (min) |',
        '|---|---:|---:|---:|---:|---:|']
    main=['temporal_boosting','conditional_fusion','equal_fusion']
    roots=[next(r for r in endpoint if r['mode']==m and r['endpoint']=='successful_root'
        and r['delay_minutes']==0 and r['horizon']==30) for m in main]
    text += [f"| {r['mode']} | {r['mean_brier']:.7f} | {r['mean_ap']:.4f} | {r['warned']} / {r['strict_warned']} | {r['false_episodes']} | {r['median_strict_lead']:.2f} |" for r in roots]
    without=[]
    for mode in main:
        selected_campaigns=[r for r in per_campaign if r['mode']==mode and r['endpoint']=='successful_root'
            and r['horizon']==30 and r['delay_minutes']==0 and r['scenario']!='wheeler']
        without.append(sum(r['false_warning_episodes'] for r in selected_campaigns))
    text += ['',
        f"Fusion reduces the total false episodes by 75% (20 to 5) at the same 4/8 timely new-warning coverage. It worsens Brier and ranking. Removing wheeler leaves false totals {without[0]} for boosting and {without[1]} for learned fusion: the aggregate improvement reverses. Equal averaging has fewer false episodes than learned fusion but only 3/8 timely new warnings and worse probability error. These competing results prevent a universal improvement claim.",
        '', '## Synthetic availability delay sensitivity','',
        'Forecasts were shifted by 1, 2 and 5 minutes with fixed calibration and thresholds. This tests stale information, not actual IDS receipt latency. Padding uses no forecast before one is available. At 15 minutes, learned fusion still starts timely new warnings in 4/8 root cases, but its median lead decreases as follows.','',
        '| Added delay (min) | New warnings / 8 | Median lead (min) | False episodes |',
        '|---|---:|---:|---:|']
    latency=[r for r in endpoint if r['mode']=='conditional_fusion' and r['endpoint']=='successful_root' and r['horizon']==15]
    text += [f"| {r['delay_minutes']} | {r['strict_warned']} | {r['median_strict_lead']:.2f} | {r['false_episodes']} |" for r in latency]
    transfer=json.loads((OUT/'cam_transfer.json').read_text())
    text += ['', '## Untouched CAM-LDS transfer diagnostic','',
        'Six distinct templates were chosen before outcome scoring. Full Wazuh streams, rather than attack-filtered manifestations, were retrieved. Three contain a published privilege-escalation tactic and three do not. The frozen AIT fox-fold base models, fusion coefficients, harrison calibration and thresholds were reused without CAM tuning. Recomputed original validation probabilities match exactly (maximum error 0.0).','',
        '| Template | Available sensor families | Pre-proxy minutes | Eligible |',
        '|---|---|---:|---|']
    for r in transfer['source_audit']:
        text.append(f"| {r['scenario']} | {', '.join(r['observed_sources'])} | {r.get('pre_endpoint_minutes',0):.1f} | {r['eligible']} |")
    text += ['',
        'At 15 minutes, duration HMM, boosting, learned fusion and equal fusion each produce **0/3 warnings** and zero false episodes. This is a negative transfer result. AMiner is absent; native Wazuh includes Suricata alerts and a different detector mix. The outcome is the first executed privilege tactic, not independently verified successful escalation. One eligible trace has no negative forecast bins at 15 minutes, so its false-alarm rate is undefined (null), not a measured zero rate. These short records cannot validate a daily alarm budget. Do not combine these cases with AIT recall or call this full-pipeline generalization.','',
        '## Decision Network and syllabus coverage','',
        '| Unit | Substantive implemented use |',
        '|---|---|',
        '| 1 | Bayesian threat-state parent with detector-count children; factorized observation likelihood and conditional fusion CPD |',
        '| 2 | Forward HMM filtering, age-expanded duration states and first-onset projection |',
        '| 3 | Onset-time chance node, response decision, delayed effectiveness and expected damage/disruption utility |','',
        'The previous 27-setting sensitivity analysis found delay-aware fusion decisions improve assumed cost in 11 settings and worsen it in 16, with negative mean improvement. Costs and effects are assumptions; no action was executed to measure prevention. Including a Decision Network does not establish improved response outcomes.','',
        '## Defensible contribution and remaining limits','',
        'The strongest scope is an endpoint-audited empirical study of multi-sensor forecasting and alarm/probability tradeoffs. The full temporal tree has 30.3% lower mean 15-minute Brier than the best single-sensor tree (AMiner), with 5/8 rather than 2/8 any-warning coverage at three false episodes for each. At five minutes, AMiner alone gives better ranking and more warnings, so the gain is horizon-dependent. The probabilistic fusion adds a conditional operational tradeoff, not a new inference algorithm.','',
        'All eight AIT campaigns were inspected during development; folds and bootstrap intervals are exploratory. The adapted HMM and fixed-budget GRU are not optimized replicas of full prior systems. Source alert generation is forensic and may have training/delivery behavior different from online IDS deployment; causal clock features alone do not prove true receipt-time availability. The legacy app and cached demonstration results remain separate from the research experiment engine.','',
        'A manuscript draft is provided in `docs/PAPER_DRAFT.md`. A strong generalized-superiority paper still needs fresh full-sensor campaigns with independently verified successful endpoints and measured availability, plus competitive validation-only tuning or faithful compatible author-code comparisons. These are concrete evidence gaps, not a promise that more tuning will improve the combination.','',
        '## Reproduction','',
        'After the original research caches and saved predictions exist, run `backend/research/run_publication_validation.ps1`. Network retrieval is opt-in via `-FetchPublicEvidence`; otherwise it uses the already downloaded selected members. Full results: `baseline_comparison.csv`, `endpoint_rescored.csv`, `cam_transfer.json`, individual forecast NPZ files and `verification.json`.','',
        '## Primary references','',
        '- [Perera Miriya Thanthrige et al., HMM alert prediction](https://arxiv.org/html/1610.07276).',
        '- [Ansari et al., GRU alert prediction](https://research.tus.ie/en/publications/gru-based-deep-learning-approach-for-network-intrusion-alert-pred/).',
        '- [AIT dataset paper, Sections 3.2 and 4](https://arxiv.org/pdf/2203.08580.pdf).',
        '- [Original AIT execution/audit data](https://zenodo.org/records/5789064).',
        '- [CAM-LDS complete scenario logs](https://zenodo.org/records/18390561).',
        '- [Withdrawn E-HiDNet preprint; excluded from validated comparisons](https://arxiv.org/abs/2601.06734).','']
    (OUT/'REPORT.md').write_text('\n'.join(text),encoding='utf-8')
    plt.rcParams.update({'font.size':9})
    fig,axes=plt.subplots(1,3,figsize=(12,3.4))
    labels=['Boosting','Learned fusion','Equal mean'];colors=['#4878a8','#cf824b','#7b9c71']
    axes[0].bar(labels,[r['false_episodes'] for r in roots],color=colors)
    axes[0].set(title='All 8 campaigns',ylabel='30-minute false episodes')
    axes[1].bar(labels,without,color=colors);axes[1].set(title='Exclude wheeler',ylabel='30-minute false episodes')
    axes[2].bar(labels,[r['mean_brier']*1000 for r in roots],color=colors)
    axes[2].set(title='Observed root endpoint',ylabel='Mean Brier × 1000 (lower is better)')
    for ax in axes:ax.tick_params(axis='x',rotation=20);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Alarm reductions depend on campaign; probability quality worsens')
    fig.tight_layout();directory=OUT/'figures';directory.mkdir(exist_ok=True)
    fig.savefig(directory/'root_warning_tradeoff.png',dpi=180);fig.savefig(directory/'root_warning_tradeoff.pdf');plt.close(fig)
    paths=list((pilot.ROOT/'backend/research').glob('*.py'))+list((pilot.ROOT/'backend/tests').glob('*.py'))
    paths+=list(OUT.glob('*.json'))+list(OUT.glob('*.csv'))+list((OUT/'predictions').glob('*.npz'))
    paths+=list((pilot.ROOT/'docs').glob('*.md'))+[pilot.ROOT/'experiments/publication_validation_protocol.md',
        pilot.ROOT/'backend/research/run_publication_validation.ps1',pilot.ROOT/'backend/research/requirements-research.txt']
    paths+=[CAM for CAM in [pilot.ROOT/'data/research/endpoint_evidence/manifest.json',pilot.ROOT/'data/research/cam_lds/manifest.json']]
    manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
        'packages':{m:importlib.metadata.version(m) for m in ['numpy','scipy','scikit-learn','matplotlib','torch','requests']},
        'sha256':{str(p.relative_to(pilot.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
                  if p.name!='reproducibility.json'},'protocol':'experiments/publication_validation_protocol.md',
        'new_adapted_baseline_folds':len(new_folds),'endpoint_rescore_rows':len(per_campaign),
        'status':'exploratory; external result is partial-sensor proxy diagnostic'}
    (OUT/'reproducibility.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Generated supplemental report, {len(rows)} baseline scores and PNG/PDF tradeoff figure',flush=True)

if __name__=='__main__':run()

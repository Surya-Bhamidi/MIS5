"""Describe selective fusion against original and matched-calibration controls."""
import csv
import hashlib
import importlib.metadata
import json
import platform
from collections import defaultdict
from datetime import datetime,timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import evidence_pilot as pilot
import robust_forecasting as robust
from run_selective_fusion import OUT,PREVIOUS
from selective_fusion import MODES
from report_robust_forecasting import aggregate
from competitive_gru import OUT as COMPARISON

FULL=robust.subset_key(robust.SENSORS)
LABELS={'raw_counts':'Raw counts-only','raw_selective':'Raw selective fusion',
    'pooled_counts':'Pooled-calibrated counts-only','pooled_state':'Pooled-calibrated BN/HMM state + counts',
    'pooled_fixed_blend':'Pooled-calibrated fixed .25 blend','pooled_selective':'Pooled-calibrated selective fusion',
    'temporal_boosting':'Original calibrated counts-only','conditional_fusion':'Original duration/tree fusion',
    'state_augmented_boosting':'Earlier single-campaign calibrated state model'}


def write_csv(name,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def table(lines,rows):
    lines+=['| Model | Mean Brier | Mean AP | Timely new warnings / 8 | False episodes | Negative warning minutes |',
        '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {LABELS[r['mode']]} | {r['mean_brier']:.7f} | {r['mean_ap']:.4f} | {r['strict_warned']} | {r['false_episodes']} | {r['negative_warning_minutes']:.0f} |")


def run():
    verification=json.loads((OUT/'verification.json').read_text());assert verification['passed']
    rows=json.loads((OUT/'scored.json').read_text());meta=json.loads((OUT/'metadata.json').read_text())
    summary=aggregate(rows,['mode','available','endpoint','horizon','budget','delay_minutes'])
    assert all(r['campaigns']==8 for r in summary)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');write_csv('summary.csv',summary)
    old=json.loads((COMPARISON/'budget_summary.json').read_text())
    previous=json.loads((PREVIOUS/'summary.json').read_text())
    def get(mode,h,budget=1,available=FULL,endpoint='successful_root',delay=0):
        return next(r for r in summary if (r['mode'],r['horizon'],r['budget'],r['available'],r['endpoint'],r['delay_minutes'])
            ==(mode,h,budget,available,endpoint,delay))
    def old_get(mode,h,budget=1):
        return next(r for r in old if (r['mode'],r['horizon'],r['budget'],r['endpoint'])==(mode,h,budget,'successful_root'))
    primary=get('pooled_selective',15);matched=get('pooled_counts',15);original=old_get('temporal_boosting',15)
    target=primary['strict_warned']>4 and primary['false_episodes']<=3
    probability_improvement=(original['mean_brier']-primary['mean_brier'])/original['mean_brier']*100
    assessment={'primary':'pooled_selective','horizon':15,'endpoint':'successful_root','budget':1,
        'timely_warning_target_met':target,'target':'more than 4/8 new warnings and at most 3 false episodes',
        'brier_improvement_vs_original_percent':probability_improvement,
        'primary_scores':primary,'matched_counts_scores':matched,'original_counts_scores':original,
        'status':'exploratory; complete published-system superiority and independent generalization unestablished'}
    fixed30=get('pooled_fixed_blend',30);original30=old_get('temporal_boosting',30)
    assessment['prespecified_fixed_blend_30_minutes']={'scores':fixed30,'original_counts_scores':original30,
        'matched_counts_scores':get('pooled_counts',30),
        'brier_improvement_vs_original_percent':100*(original30['mean_brier']-fixed30['mean_brier'])/original30['mean_brier'],
        'status':'conditional positive control result, not a test-selected replacement for the primary variant'}
    (OUT/'assessment.json').write_text(json.dumps(assessment,indent=2),encoding='utf-8')
    lines=['# Selective fusion: completed campaign-validation experiment','',
        'The fixed .25 blend is now the [current research preset](../../docs/CURRENT_VERSION.md), with 30-minute warning as its primary use case and further advancements deferred. [Frozen artifacts](../current_version/README.md) preserve its fold predictions, calibrators and thresholds. Choosing that development preset after inspecting results does not change the adaptive primary result below.','',
        f"**Primary result:** selective fusion gives {primary['strict_warned']}/8 timely 15-minute root warnings and {primary['false_episodes']} false episodes, versus {original['strict_warned']}/8 and {original['false_episodes']} for original calibrated counts-only. Mean Brier changes from {original['mean_brier']:.7f} to {primary['mean_brier']:.7f} ({probability_improvement:+.1f}% improvement; negative means worse). The stated warning target {'is met' if target else 'is not met'}.",'',
        f"Under the same new calibration procedure, counts-only gives {matched['strict_warned']}/8 warnings, {matched['false_episodes']} false episodes and Brier {matched['mean_brier']:.7f}. This is the controlled reference for assessing the additional BN/HMM contribution. Neither comparison establishes a previously unpublished architecture or superiority over complete published systems.",'',
        'This round was specified after inspecting the previous failed blends and confirmation model. Every AIT campaign and CAM proxy was already known. Nested fitting exclusion prevents direct test-label fitting, but does not make repeatedly inspected test cases an independent confirmation set. All six fixed variants and previous negative results are retained.','',
        '## Implemented pipeline','',
        '```mermaid','flowchart LR',
        '    A[Available sensor counts] --> B[Counts-only boosted trees]',
        '    A --> C[BN observation likelihood]',
        '    C --> D[Forward HMM state belief]',
        '    D --> E[State-augmented boosted trees]',
        '    A --> E',
        '    B --> F[Fitting-campaign selected weights by horizon and sensor subset]',
        '    E --> F',
        '    F --> G[Pooled fitting-campaign sigmoid calibration]',
        '    G --> H[Separate validation alarm thresholds]',
        '    G --> I[Decision Network with delay and assumed utility]',
        '```','',
        'For each outer split, six campaigns fit predictors/selection/calibration, the next campaign chooses alarm thresholds, and one campaign is scored. Each of the six fitting campaigns obtains base and state-model forecasts from predictors fitted to the other five. Within those five, augmented training features use state models fitted to four campaigns. Vocabularies and state fitting exclude the held forecast campaign. Existing six-campaign outer expert raw forecasts are preserved exactly.','',
        'For each sensor subset and horizon, choose a raw blend weight from {0,.1,.25,.5,1} using the mean six-campaign held-out Brier normalized by counts-only Brier plus .01 times the weight. Calibration follows selection, using those six fitting-campaign predictions with equal total weight per campaign. Sigmoid C=1 and all tree settings are fixed. A negative fitted slope is replaced by the weighted target prior. Monotonicity repair operates along forecast horizons, never through future time.','',
        'Weights and calibrators do not use the outer validation or test labels. Thresholds still use the separate single outer validation campaign, exactly as in the reference protocol. Held fitting predictions are reused for choosing weights and fitting final calibrators; five-campaign fitting forecasts versus six-campaign application can shift distributions. Weight selection scores individual raw horizons before the joint monotonicity repair and calibration; those downstream operations may change the error. These remain limitations, so fitting-criterion improvement is not a guarantee about final test forecasts.','',
        'The public `predict_selective` API combines actual fitted branches, returns state belief and modeled expected losses, and recommends a Decision Network action without executing it. It retains explicit no-sensor abstention. Static availability is declared, not inferred from measured heartbeats.','',
        '## Common full-input comparisons','',
        'All tables use successful-root endpoints, strict warning episode starts, and the same validation budget of one false episode per 24 negative hours with at most five negative warning minutes. This budget is a validation constraint, not a guaranteed test alarm rate. Lower Brier and higher AP are better. Root scoring is a sensitivity rescore of models trained for scheduled escalation.','']
    for h in [5,15,30]:
        lines += [f'### {h}-minute forecasts','']
        originals=[old_get(m,h) for m in ['temporal_boosting','conditional_fusion']] if h in [15,30] else []
        table(lines,originals+[get(m,h) for m in MODES]);lines+=['']
        base=get('pooled_counts',h);new=get('pooled_selective',h)
        delta=(base['mean_brier']-new['mean_brier'])/base['mean_brier']*100
        lines += [f"Selective fusion versus matched pooled counts: Brier improvement {delta:+.1f}%; new warnings {base['strict_warned']} → {new['strict_warned']}; false episodes {base['false_episodes']} → {new['false_episodes']}. A warning gain paired with larger alarm burden or worse probability error is a tradeoff.",'']
    lines+=['![Probability and warning comparison](figures/selective_fusion_tradeoffs.png)','',
        '## Fixed .25 blend: a conditional 30-minute positive result','',
        'This control was specified before scoring, rather than added after inspecting the adaptive selector. It combines 75% raw counts-only risk and 25% raw BN/HMM-state augmented risk, then applies the pooled fitting-campaign calibrator. It keeps substantive state-model input in every fold. The adaptive selective variant remains the primary result; this control is a separately identified exploratory finding.','']
    table(lines,[original30,old_get('conditional_fusion',30),get('pooled_counts',30),fixed30])
    delta=assessment['prespecified_fixed_blend_30_minutes']['brier_improvement_vs_original_percent']
    pooled30=get('pooled_counts',30)
    incremental=100*(pooled30['mean_brier']-fixed30['mean_brier'])/pooled30['mean_brier']
    lines+=['',f"Against original counts-only, this control gives {fixed30['strict_warned']}/8 versus {original30['strict_warned']}/8 timely warnings, {fixed30['false_episodes']} versus {original30['false_episodes']} false episodes and {delta:.2f}% lower mean Brier. Mean AP is {fixed30['mean_ap']:.4f} versus {original30['mean_ap']:.4f}. Against matched pooled counts, the blend recovers two additional timely cases, but false episodes rise from {pooled30['false_episodes']} to {fixed30['false_episodes']}; its Brier gain is only {incremental:.2f}%. Much of the probability gain versus the original model therefore comes from calibration. Original duration fusion has fewer false episodes than this blend, so complete pipeline superiority is not established.",'',
        'The aggregate false-episode reduction versus original counts depends on wheeler, where the original model produces 17 episodes. Excluding that case, original counts has two false episodes and the fixed blend has five; the direction reverses. The additional timely case relative to original counts is santos. This supports a limited warning/probability tradeoff, not a large robust all-condition gain.','',
        '## Calibration recovery versus an actual fusion gain','',
        '| Horizon | Earlier state-model Brier | Pooled state-model Brier | Relative improvement |',
        '|---|---:|---:|---:|']
    for h in [5,15,30]:
        before=next(r for r in previous if (r['mode'],r['available'],r['endpoint'],r['horizon'],r['budget'],r['delay_minutes'])
            ==('state_augmented_boosting',FULL,'successful_root',h,1,0))
        after=get('pooled_state',h);delta=(before['mean_brier']-after['mean_brier'])/before['mean_brier']*100
        lines.append(f"| {h} min | {before['mean_brier']:.7f} | {after['mean_brier']:.7f} | {delta:+.1f}% |")
    lines+=['','Both rows apply to the same six-campaign outer state-model raw forecasts. This comparison isolates the new calibration procedure. Recovering from a failed earlier variant is not itself improvement over the strongest counts-only reference. The pooled-counts ablation separates calibration gains from state fusion.','',
        '## Actual BN/HMM contribution','',
        '| Test campaign | Weights at 1 / 2 / 5 / 10 / 15 / 30 min | Changed raw minutes at 15 / 30 min |',
        '|---|---|---:|']
    for m in meta:
        if m['available']!=FULL:continue
        values=' / '.join(f'{w:g}' for w in m['weights']);contribution=m['state_contribution']
        lines.append(f"| {m['test']} | {values} | {contribution['15']['raw_changed_minutes']} / {contribution['30']['raw_changed_minutes']} |")
    lines+=['','Unit 1 BN likelihood and Unit 2 causal HMM states feed the augmented branch; Unit 3 uses the fused onset distribution in delayed-action expected loss. Inner-fit tree audits document actual state-feature splits. Zero weights mean no direct state contribution for that horizon, although monotonicity repair can propagate a lower-horizon contribution upward. Computing a diagnostic alone is not an improvement. `metadata.json` records exact weights and changed prediction minutes for every subset.','',
        '## Alarm-budget sensitivity','',
        '| Horizon | Budget / 24h | Original counts new / false | Pooled counts new / false | Selective fusion new / false |',
        '|---|---:|---:|---:|---:|']
    for h in [15,30]:
        for b in [0,.25,1,4]:
            entries=[old_get('temporal_boosting',h,b),get('pooled_counts',h,b),get('pooled_selective',h,b)]
            cells=' | '.join(f"{r['strict_warned']} / {r['false_episodes']}" for r in entries)
            lines.append(f'| {h} min | {b:g} | {cells} |')
    lines+=['','## Campaign dependence and paired differences','',
        '| 30-min model, excluding wheeler | New warnings / 7 | False episodes |',
        '|---|---:|---:|']
    for mode in ['pooled_counts','pooled_fixed_blend','pooled_selective']:
        group=[r for r in rows if (r['mode'],r['available'],r['endpoint'],r['horizon'],r['budget'],r['delay_minutes'])
            ==(mode,FULL,'successful_root',30,1,0) and r['scenario']!='wheeler']
        lines.append(f"| {LABELS[mode]} | {sum(r['strict_warning_recall'] for r in group)} | {sum(r['false_warning_episodes'] for r in group)} |")
    pairs=[]
    for h in [5,15,30]:
        for metric,sign in [('brier',-1),('average_precision',1),('strict_warning_recall',1),('false_warning_episodes',-1)]:
            changes={}
            for n in pilot.SCENARIOS:
                def case(mode):return next(r for r in rows if (r['scenario'],r['mode'],r['available'],r['endpoint'],r['horizon'],r['budget'],r['delay_minutes'])
                    ==(n,mode,FULL,'successful_root',h,1,0))
                changes[n]=sign*(case('pooled_selective')[metric]-case('pooled_counts')[metric])
            v=np.array(list(changes.values()));draws=np.random.default_rng(1729).integers(0,8,size=(20000,8))
            pairs.append({'horizon':h,'metric':metric,'campaign_improvements':changes,'mean_improvement':float(v.mean()),
                'improved_campaigns':int(np.sum(v>1e-12)),'worse_campaigns':int(np.sum(v<-1e-12)),
                'descriptive_bootstrap_95_interval':np.quantile(v[draws].mean(axis=1),[.025,.975]).tolist(),
                'status':'descriptive; related campaigns and repeated development'})
    (OUT/'paired_comparisons.json').write_text(json.dumps(pairs,indent=2),encoding='utf-8')
    lines+=['','Eight related campaigns, overlapping fitting sets and prior outcome inspection limit uncertainty estimates. Paired differences and descriptive bootstrap intervals are in `paired_comparisons.json`; they are not confirmatory significance claims.','',
        '## Sensor subsets at 15 minutes','',
        '| Available sensors | Pooled counts timely / false | Selective fusion timely / false | Counts Brier | Selective Brier |',
        '|---|---:|---:|---:|---:|']
    for available in robust.SUBSETS:
        key=robust.subset_key(available);a=get('pooled_counts',15,available=key,endpoint='scheduled_onset')
        b=get('pooled_selective',15,available=key,endpoint='scheduled_onset')
        lines.append(f"| {key} | {a['strict_warned']} / {a['false_episodes']} | {b['strict_warned']} / {b['false_episodes']} | {a['mean_brier']:.7f} | {b['mean_brier']:.7f} |")
    lines+=['','This table uses scheduled-onset scoring to retain comparability with earlier outage replays. Both methods use matching static availability, nested fitting forecasts and the same calibration/threshold procedure. Modified availability is a paired stress condition, not a new independent attack.','',
        'Without Wazuh, selective fusion produces 3/8 timely scheduled-onset warnings versus 2/8 for pooled counts, at one false episode each. Brier decreases by 3.13% and AP rises from .6613 to .7197, while negative warning duration increases from 19 to 25 minutes. The older availability-specific single-campaign calibrated counts expert already gave 3/8 at one false episode, but with higher Brier (.0016708 versus .0014548) and lower AP (.6661 versus .7197). This is incremental state benefit against matched pooled counts plus improved probability/ranking against the earlier expert, with a warning-duration cost. It is not a large all-condition gain.','',
        '## Frozen CAM proxy diagnostic','',
        '| Method | 15-min timely warnings / 3 | False episodes | 30-min timely warnings / 3 | False episodes |',
        '|---|---:|---:|---:|---:|']
    transfer=json.loads((OUT/'cam_transfer.json').read_text())
    for mode in MODES:
        cells=[]
        for h in [15,30]:
            group=[r for r in transfer if r['mode']==mode and r['horizon']==h and r['budget']==1]
            cells.extend([str(sum(r['strict_warning_recall'] for r in group)),str(sum(r['false_warning_episodes'] for r in group))])
        lines.append(f"| {LABELS[mode]} | {' | '.join(cells)} |")
    lines+=['','AIT-only fox-fold fitting/selection/calibration and harrison thresholds transfer without CAM tuning. AMiner is absent, Wazuh and Suricata are declared present. These three known outcomes are executed-tactic proxies, not verified successful compromises. At 30 minutes there is only one minute of negative exposure across the records; no daily budget or generalization conclusion follows from zero false episodes.','',
        '## Decision Network under the original assumed settings','',
        '| Model | Lower cost versus delay-blind / 27 | Higher cost / 27 | Mean assumed improvement |',
        '|---|---:|---:|---:|']
    decisions=json.loads((OUT/'decisions.json').read_text());utility=[]
    for mode in MODES:
        groups=defaultdict(list)
        for r in decisions:
            if r['available']==FULL and r['mode']==mode:groups[(r['damage'],r['effect_scale'],r['disruption_scale'])].append(r['improvement'])
        means=[float(np.mean(v)) for v in groups.values()]
        r={'mode':mode,'improved_settings':sum(v>1e-12 for v in means),'worse_settings':sum(v<-1e-12 for v in means),
            'mean_assumed_improvement':float(np.mean(means))};utility.append(r)
        lines.append(f"| {LABELS[mode]} | {r['improved_settings']} | {r['worse_settings']} | {r['mean_assumed_improvement']:.7g} |")
    (OUT/'decision_summary.json').write_text(json.dumps(utility,indent=2),encoding='utf-8')
    lines+=['','Damage {10,20,50}, efficacy scales {.5,.8,1} and disruption {.5,1,2} match earlier analysis. These are framewise hypothetical costs and assumed action effects, with no executed defenses or measured prevention. A policy rescore cannot establish effective attack prevention.','',
        '## What can be claimed','',
        'The numerical comparisons establish only the observed differences under this fixed exploratory protocol. A gain relative to the failed state model is calibration recovery; a gain relative to pooled counts is evidence of incremental state fusion on these cases. Neither implies consistent superiority across metrics, conditions or complete published systems. The selected primary variant is retained regardless of whether another control has a better test result.','',
        'Fresh independent campaigns with long no-target intervals, online sensor receipt evidence and verified outcomes remain needed for stronger early-warning claims. Physical response effects remain unmeasured. Conventional weighted fusion and cross-validated calibration do not establish first-ever architecture; the literature limitations in `docs/NOVELTY_AUDIT.md` still apply.','',
        '## Reproduce and verify','',
        'Run `backend/research/run_selective_fusion.ps1`. Existing AIT caches, audited endpoints and previous raw expert forecasts are prerequisites. Four independent fitting processes each use two numerical threads; `-Workers 1` runs sequentially. Valid caches resume with source/data hashes. No data are fetched and no packages are installed.','',
        f"Verification passed {verification['regression_tests']} tests, {verification['inner_availability_fits']} inner availability fits across {verification['unique_five_campaign_fits']} distinct five-campaign sets, {verification['outer_availability_settings']} outer availability settings, {verification['validation_thresholds']} thresholds, {verification['endpoint_budget_delay_rows']} score rows, {verification['assumed_decision_settings']} assumed decision rows and {verification['external_proxy_rows']} external rows. Weights, calibrators, forecasts and metrics were independently reconstructed. Hashes are in `reproducibility.json`.",'',
        'Method references: [official probability calibration guidance](https://scikit-learn.org/stable/modules/calibration.html) and [group-aware cross-validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html). These support established evaluation practices, not an originality claim.','']
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,h in zip(axes,[15,30]):
        compare=[old_get('temporal_boosting',h),old_get('conditional_fusion',h),get('pooled_counts',h),get('pooled_fixed_blend',h),get('pooled_selective',h)]
        names=['Original counts','Original fusion','Pooled counts','Fixed .25 blend','Selective fusion']
        ax.bar(names,[r['mean_brier']*1000 for r in compare],color=['#4477aa','#bb9977','#66aa88','#aa77bb','#dd8844'])
        for i,r in enumerate(compare):ax.text(i,r['mean_brier']*1000,f"{r['strict_warned']}/8 new; {r['false_episodes']} false",ha='center',va='bottom',fontsize=7)
        ax.set(title=f'{h}-minute root endpoint',ylabel='Brier × 1000 (lower is better)');ax.tick_params(axis='x',rotation=15);ax.margins(y=.25)
    fig.suptitle('Selective fusion and matched calibration controls');fig.tight_layout()
    directory=OUT/'figures';directory.mkdir(exist_ok=True)
    fig.savefig(directory/'selective_fusion_tradeoffs.png',dpi=180);fig.savefig(directory/'selective_fusion_tradeoffs.pdf');plt.close(fig)
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    paths=list(OUT.rglob('*'))+list((pilot.ROOT/'backend/research').glob('*.py'))+list((pilot.ROOT/'backend/tests').glob('*.py'))
    paths+=list((pilot.ROOT/'docs').glob('*.md'))+[pilot.ROOT/'experiments/selective_fusion_protocol.md',pilot.ROOT/'backend/research/run_selective_fusion.ps1']
    paths+=list((PREVIOUS/'predictions').glob('ait_*_available_boosting.npz'))+list((PREVIOUS/'predictions').glob('ait_*_state_augmented_boosting.npz'))
    paths += [COMPARISON/'budget_summary.json',PREVIOUS/'summary.json',pilot.ROOT/'experiments/publication_validation/endpoint_evidence.json']
    paths+=list((pilot.ROOT/'data/research/extended').glob('ait_*_v2.npz'))
    manifest={'utc':datetime.now(timezone.utc).isoformat(),'protocol':'experiments/selective_fusion_protocol.md',
        'python':platform.python_version(),
        'packages':{name:importlib.metadata.version(name) for name in ['numpy','scipy','scikit-learn','matplotlib','threadpoolctl']},
        'status':'exploratory; already inspected campaigns; assumed effects',
        'sha256':{str(p.relative_to(pilot.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
            if p.is_file() and p.name!='reproducibility.json' and '__pycache__' not in p.parts}}
    (OUT/'reproducibility.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(assessment,indent=2),flush=True)


if __name__=='__main__':run()

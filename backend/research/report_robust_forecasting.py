"""Report revised pipeline improvements and losses without choosing on test."""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime,timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import evidence_pilot as pilot
import extended_study as study
from run_robust_forecasting import OUT,MODES
from audit_endpoints import OUT as VALIDATION
from competitive_gru import OUT as COMPARISON
from robust_forecasting import SENSORS,subset_key

FULL=subset_key(SENSORS)
LABELS={'available_boosting':'Availability-specific boosting',
    'state_augmented_boosting':'BN/HMM-state + boosting',
    'validated_state_fusion':'Validation-selected state blend',
    'state_confirmed_alarm':'Probability-preserving state confirmation',
    'clock_only_boosting':'Elapsed-clock-only boosting',
    'long_history_boosting':'Counts + longer history + elapsed clock',
    'temporal_boosting':'Original boosting','conditional_fusion':'Original duration/tree fusion',
    'validation_selected_gru':'Longer validation-selected GRU'}

def aggregate(rows,keys):
    groups=defaultdict(list)
    for r in rows:groups[tuple(r[k] for k in keys)].append(r)
    result=[]
    for identity,group in sorted(groups.items()):
        leads=[r['strict_lead_minutes'] for r in group if r['strict_lead_minutes'] is not None]
        result.append(dict(zip(keys,identity),campaigns=len(group),
            mean_brier=float(np.mean([r['brier'] for r in group])),
            mean_ap=float(np.mean([r['average_precision'] for r in group])),
            warned=sum(r['warning_recall'] for r in group),strict_warned=sum(r['strict_warning_recall'] for r in group),
            false_episodes=sum(r['false_warning_episodes'] for r in group),
            negative_warning_minutes=sum(r['negative_warning_minutes'] for r in group),
            median_strict_lead=None if not leads else float(np.median(leads))))
    return result

def csv_write(name,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def table(lines,rows):
    lines+=['| Model | Mean Brier | Mean AP | Timely new warnings / 8 | False episodes | Median timely lead (min) |',
        '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lead='—' if r['median_strict_lead'] is None else f"{r['median_strict_lead']:.2f}"
        lines.append(f"| {LABELS.get(r['mode'],r['mode'])} | {r['mean_brier']:.7f} | {r['mean_ap']:.4f} | {r['strict_warned']} | {r['false_episodes']} | {lead} |")

def run():
    verification=json.loads((OUT/'verification.json').read_text());assert verification['passed']
    scored=json.loads((OUT/'scored.json').read_text());metadata=json.loads((OUT/'metadata.json').read_text())
    decisions=json.loads((OUT/'decisions.json').read_text());cam=json.loads((OUT/'cam_transfer.json').read_text())
    gate_scores=json.loads((OUT/'gate_scored.json').read_text())
    gate_choices=json.loads((OUT/'gate_selection.json').read_text())
    gate_decisions=json.loads((OUT/'gate_decisions.json').read_text())
    gate_cam=json.loads((OUT/'gate_cam.json').read_text())
    context_scores=[dict(r,available=FULL,delay_minutes=0) for r in json.loads((OUT/'context_scored.json').read_text())]
    folds=json.loads((OUT/'fold_results.json').read_text())
    keys=['mode','available','endpoint','horizon','budget','delay_minutes']
    summary=aggregate(scored,keys);assert all(r['campaigns']==8 for r in summary)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');csv_write('summary.csv',summary)
    gate_summary=aggregate(gate_scores,keys);context_summary=aggregate(context_scores,keys)
    for name,rows in [('gate_summary',gate_summary),('context_summary',context_summary)]:
        (OUT/(name+'.json')).write_text(json.dumps(rows,indent=2),encoding='utf-8');csv_write(name+'.csv',rows)
    old=json.loads((COMPARISON/'budget_summary.json').read_text())
    def get(mode,h,budget=1,available=FULL,delay=0,endpoint='successful_root'):
        return next(r for r in summary if (r['mode'],r['horizon'],r['budget'],r['available'],r['delay_minutes'],r['endpoint'])
            ==(mode,h,budget,available,delay,endpoint))
    def old_get(mode,h,budget=1):
        return next(r for r in old if (r['mode'],r['horizon'],r['budget'],r['endpoint'])==(mode,h,budget,'successful_root'))
    # Verify the fair unchanged full-input reference, including strict policies.
    for h in [15,30]:
        for budget in [0,.25,1,4]:
            a=get(MODES[0],h,budget);b=old_get('temporal_boosting',h,budget)
            for key in ['mean_brier','mean_ap','strict_warned','false_episodes']:
                assert abs(a[key]-b[key])<1e-12,(h,budget,key)
    natural=[m for m in metadata if m['available']==FULL]
    lines=['# Revised BN/HMM forecasting: completed improvement analysis','',
        'A later development round is complete: [selective fusion and pooled campaign calibration](../selective_fusion/REPORT.md). It finds a conditional positive 30-minute result for a prespecified .25 state blend and an outage-specific selective-fusion gain, while its adaptive 15-minute primary target fails. The fixed first-revision results below are retained.','',
        '**Verdict: explicit sensor availability improves some outage warnings, but the revised BN/HMM combination does not surpass the original boosting model overall. Full-input 15-minute warning coverage falls from 4/8 to 2/8, false episodes rise from 3 to 15, and mean Brier error is about four times larger. The probability-preserving alarm revision selects no HMM confirmation at 15/30 minutes, so it retains the baseline results without an additional HMM gain.**','',
        'This report retains every fixed revised variant and every negative result. All AIT campaigns and the three existing CAM diagnostic targets had already been inspected; this is exploratory. New code does not establish independent confirmation, unique architecture, publication acceptance or superiority over complete published systems.','',
        '## What changed','',
        'The original pipeline fused a duration-HMM onset forecast and boosting probabilities. The revised pipeline uses a BN stage-parent/count-child observation likelihood to infer a causal HMM state posterior, then supplies that posterior and its trailing summaries to boosting alongside the original count history. State features for each fitting campaign come from HMMs fitted to the other five fitting campaigns; validation/test filtering uses the six fitting campaigns. No test stage labels or attack outcome enter prediction.','',
        'Available detector families are explicit inputs. Experts are fitted for all seven nonempty sensor subsets, omitting unavailable sensors from both the BN likelihood and tree inputs. Missing sensors are not filled with fake alerts or interpreted as observed zero counts. With no sensors the API abstains. The current experiment supplies known static availability; measured heartbeats and dynamic outage handling are not established.','',
        'Three fixed variants are reported: counts-only availability experts; counts plus inferred BN/HMM state features; and a validation-selected mixture of those two. The mixture selects one coefficient across all horizons from {0,.25,.5,.75,1}, minimizing normalized validation Brier plus a .01 weight penalty. Calibration and selection reuse the same validation campaign. The fallback can omit state information from the risk forecast; it cannot guarantee test improvement.','',
        'Unit 3 remains the Decision Network using the forecast onset distribution, response delay, assumed effect and damage/disruption utility. The same original 27 cost/effect settings were rescored. No defensive action was physically executed.','',
        'The first protocol fixed the three forecast variants before their complete results. Longer-history/clock controls were specified as supplementary diagnostics. After observing the revised probability losses, a second recorded protocol separated the counts-only probability forecast from optional BN/HMM alarm confirmation. This second round is explicitly adaptive exploration; it is not an untouched confirmation experiment. All failed first-round variants remain in the report.','',
        '## Full-input comparisons before verified successful root outcomes','',
        'All rows below use the same strict validation-selected alarm policy: budget 1 false episode per 24 negative hours and at most five negative warning minutes. Timely warning episodes must BEGIN inside the forecast window. Original fusion is rescored under this rule, so its totals can differ from its older permissive-threshold report. Model fitting still targets scheduled escalation; root scoring is an endpoint sensitivity rescore. Lower Brier is better; higher AP is better.','']
    main=[]
    for h in [15,30]:
        lines += [f'### {h}-minute forecasts','']
        rows=[old_get('temporal_boosting',h),old_get('conditional_fusion',h),old_get('validation_selected_gru',h)]+[get(m,h) for m in MODES[1:]]
        table(lines,rows);main+=rows
        base=old_get('temporal_boosting',h);old_f=old_get('conditional_fusion',h)
        for mode in MODES[1:]:
            new=get(mode,h)
            delta_base=(base['mean_brier']-new['mean_brier'])/base['mean_brier']*100
            delta_old=(old_f['mean_brier']-new['mean_brier'])/old_f['mean_brier']*100
            lines += ['',f"{LABELS[mode]}: Brier improvement versus boosting {delta_base:+.1f}%, versus original fusion {delta_old:+.1f}%; timely coverage {new['strict_warned']}/8 and {new['false_episodes']} false episodes. A negative percentage means deterioration."]
        lines+=['']
    lines+=['![Probability error and timely warning tradeoffs](figures/revised_probability_warning_tradeoff.png)','',
        '### Five-minute forecast: a limited positive result','']
    table(lines,[get(m,5) for m in MODES])
    lines+=['','The state variants produce one timely new warning versus zero for counts-only, and higher mean AP, but substantially worse Brier. One recovered case is a conditional warning/ranking gain, not an across-metric improvement.','',
        '## Longer-history and elapsed-clock controls','',
        'The elapsed-clock control uses only minutes since the first recorded bin. The longer-history control augments the original counts with trailing 180-, 360- and 1440-minute means and elapsed clock. It uses the same fitting campaigns, model settings, validation calibration and alarm rule. These controls test whether added temporal context alone can explain improvements; elapsed recording time may itself be dataset-specific. Neither control was eligible for the earlier blend selection.','']
    for h in [15,30]:
        lines += [f'### {h}-minute control comparison','']
        control=[r for r in context_summary if r['horizon']==h and r['budget']==1 and r['endpoint']=='successful_root']
        table(lines,[get(MODES[0],h)]+control+[get(MODES[1],h)])
        lines+=['']
    lines+=['Longer history improves 30-minute mean AP relative to the original count model, but produces no timely new warnings at this policy and has higher Brier. Elapsed-clock-only forecasts perform poorly. These results do not establish that BN/HMM state features are the best way to add temporal information.','',
        '## Probability-preserving alarm revision','',
        'The second revision preserves availability-specific boosting probabilities exactly. A separate alarm branch may require posterior mass in the last two HMM stages to exceed 0, .5 or .9. Probability error and ranking are evaluated on the unchanged probabilities, not on the masked alarm score. Validation chooses the confirmation level and risk threshold under the same strict alarm budget; level 0 disables confirmation and wins ties. The BN and HMM therefore have a tested candidate role, not an assumed improvement.','',
        '| Horizon | Nonzero confirmations selected / 8 | Timely new warnings / 8 | False episodes | Suppressed warning minutes |',
        '|---|---:|---:|---:|---:|']
    for h in [15,30]:
        choices=[r for r in gate_choices if r['available']==FULL and r['horizon']==h and r['budget']==1]
        group=[r for r in gate_scores if r['available']==FULL and r['horizon']==h and r['budget']==1 and r['endpoint']=='successful_root']
        assert len(choices)==8 and all(r['chosen']['level']==0 for r in choices)
        lines.append(f"| {h} min | {sum(r['chosen']['level']>0 for r in choices)} | {sum(r['strict_warning_recall'] for r in group)} | {sum(r['false_warning_episodes'] for r in group)} | {sum(r['suppressed_warning_minutes'] for r in group)} |")
    primary_choices=[r for r in gate_choices if r['horizon'] in [15,30]]
    assert all(r['chosen']['level']==0 for r in primary_choices)
    lines+=['','At both main horizons, every tested availability subset and all four validation budgets select level 0. Therefore this revision preserves the baseline, including its failures; it supplies no demonstrated additional BN/HMM warning contribution. A module being computed does not establish a useful contribution from that module. Complete choices, including other horizons, are retained in `gate_selection.json`; `gate_summary.csv` includes all endpoint/subset/policy results.','']
    lines+=['## Syllabus participation and what was selected','',
        '| Unit | Actual implemented role |', '|---|---|',
        '| 1 | Fitting-only BN count conditional tables and observation likelihood, omitting missing children; fixed tempered evidence |',
        '| 2 | Forward HMM state belief and causal trailing state summaries supplied to the augmented tree |',
        '| 3 | Onset-distribution chance node, delayed-response decision and expected loss |','',
        '| Test campaign | Selected state-augmented weight | State-feature splits at 15 / 30 min |', '|---|---:|---:|']
    for m in natural:
        usage={r['horizon']:r['splits_using_state_features'] for r in m['state_feature_usage']}
        lines.append(f"| {m['test']} | {m['blend']['selected_weight']} | {usage[15]} / {usage[30]} |")
    lines+=['',
        'The split audit establishes actual use of state features in the augmented model. A selected mixture weight of zero means the risk branch falls back to counts-only; that case does not demonstrate additional HMM predictive value, even though state diagnostics are computed. All augmented-model results are retained separately.','',
        '## Alarm-policy sensitivity','',
        '| Horizon | Validation budget / 24h | Original boosting new / false | Original fusion new / false | State-augmented new / false | Selected blend new / false |',
        '|---|---:|---:|---:|---:|---:|']
    for h in [15,30]:
        for budget in [0,.25,1,4]:
            values=[old_get('temporal_boosting',h,budget),old_get('conditional_fusion',h,budget),get(MODES[1],h,budget),get(MODES[2],h,budget)]
            cells=' | '.join(f"{r['strict_warned']} / {r['false_episodes']}" for r in values)
            lines.append(f'| {h} min | {budget:g} | {cells} |')
    lines+=['','## Campaign dependence','',
        '| Model, 30 min at budget 1 | Timely new warnings excluding wheeler / 7 | False episodes excluding wheeler |',
        '|---|---:|---:|']
    for mode in MODES:
        group=[r for r in scored if (r['mode'],r['available'],r['endpoint'],r['horizon'],r['budget'],r['delay_minutes'])
            ==(mode,FULL,'successful_root',30,1,0) and r['scenario']!='wheeler']
        lines.append(f"| {LABELS[mode]} | {sum(r['strict_warning_recall'] for r in group)} | {sum(r['false_warning_episodes'] for r in group)} |")
    comparisons=[]
    for mode in MODES[1:]:
        for h in [5,15,30]:
            for metric,sign in [('brier',-1),('average_precision',1),('strict_warning_recall',1),('false_warning_episodes',-1)]:
                changes={}
                for scenario in pilot.SCENARIOS:
                    def case(m):return next(r for r in scored if (r['scenario'],r['mode'],r['available'],r['endpoint'],r['horizon'],r['budget'],r['delay_minutes'])
                        ==(scenario,m,FULL,'successful_root',h,1,0))
                    changes[scenario]=sign*(case(mode)[metric]-case(MODES[0])[metric])
                values=np.array(list(changes.values()));draws=np.random.default_rng(1729).integers(0,8,size=(20000,8))
                comparisons.append({'mode':mode,'baseline':MODES[0],'horizon':h,'metric':metric,
                    'mean_improvement':float(values.mean()),'improved_campaigns':int(np.sum(values>1e-12)),
                    'worse_campaigns':int(np.sum(values<-1e-12)),'campaign_improvements':changes,
                    'descriptive_bootstrap_95_interval':np.quantile(values[draws].mean(axis=1),[.025,.975]).tolist(),
                    'status':'descriptive only; common templates and repeatedly inspected outcomes'})
    (OUT/'paired_comparisons.json').write_text(json.dumps(comparisons,indent=2),encoding='utf-8')
    lines+=['',
        'Paired per-campaign differences and descriptive bootstrap intervals are in `paired_comparisons.json`. Eight related campaigns, overlapping fits and repeated exploratory comparisons do not justify confirmatory significance or independence claims.','',
        '## Complete sensor removal','',
        'The following comparison uses scheduled escalation at 15 minutes, so it can be compared with the original outage experiment. Old thresholds were unchanged natural-validation thresholds and permissive warning coverage; new thresholds use matching-availability validation and strict starts. This evaluates a complete revised availability/selection policy, not just a single inference change. The new counts-only expert is the fair ablation for the BN/HMM state branch.','',
        '| Missing sensor | Old boosting any / false | Old fusion any / false | Available-counts expert new / false | State-augmented new / false | Selected blend new / false |',
        '|---|---:|---:|---:|---:|---:|']
    old_stress=json.loads((study.OUT/'ait_sensor_stress.json').read_text())
    for missing in SENSORS:
        available=subset_key(set(SENSORS)-{missing})
        olds=[]
        for mode in ['temporal_boosting','conditional_fusion']:
            group=[r['calibrated']['15'] for r in old_stress if r['mode']==mode and r['dropped_sensor']==missing]
            olds.append(f"{sum(r['warning_recall'] for r in group)} / {sum(r['false_warning_episodes'] for r in group)}")
        news=[get(m,15,1,available,0,'scheduled_onset') for m in MODES]
        cells=' | '.join(olds+[f"{r['strict_warned']} / {r['false_episodes']}" for r in news])
        lines.append(f'| {missing} | {cells} |')
    lines+=['','Root-endpoint subset comparisons, including single remaining sensors, are retained in `summary.csv`. A sensor-removal replay is a stress condition of the same campaign, not an independent attack. No-sensor input abstains; abstention is not counted as a successful warning.','',
        'The clearest outage gain is removal of Wazuh: the new counts-only availability expert recovers 3/8 timely warnings at one false episode, compared with zero old warnings. That gain belongs to the availability-specific counts/selection policy. BN/HMM features retain 3/8 but raise false episodes to 28 (selected blend: 27). Without AMiner, the BN/HMM models recover 2/8 versus 0/8 for the matching counts-only expert, while false episodes rise from 3 to 13. This is a warning-coverage/false-alarm tradeoff, not general robustness superiority.','',
        '## Frozen external diagnostic','',
        'CAM receives the fox-fold expert trained on the six AIT fitting campaigns with Wazuh/Suricata declared available. AMiner remains absent. AIT harrison supplies calibration, selected weight and thresholds. CAM outcomes never select a model or threshold. The three known targets remain executed-tactic proxies; none has been upgraded to a validated successful endpoint.','',
        '| Method | 15-min timely / any warnings, out of 3 | False episodes | 30-min timely / any warnings, out of 3 | False episodes |',
        '|---|---:|---:|---:|---:|']
    cam_totals={}
    for mode in list(MODES)+['state_confirmed_alarm']:
        cells=[]
        for h in [15,30]:
            group=[r for r in cam+gate_cam if (r['mode'],r['horizon'],r['budget'])==(mode,h,1)]
            totals={'strict_warned':sum(r['strict_warning_recall'] for r in group),'warned':sum(r['warning_recall'] for r in group),
                'false_episodes':sum(r['false_warning_episodes'] for r in group)}
            cam_totals[(mode,h)]=totals;cells+=[f"{totals['strict_warned']} / {totals['warned']}",str(totals['false_episodes'])]
        lines.append(f"| {LABELS[mode]} | {' | '.join(cells)} |")
    lines+=['',
        'All revised methods still warn on 0/3 at 15 minutes. At 30 minutes the state-augmented expert and selected blend each warn on 1/3, whereas the matching counts-only expert warns on none; the recovered warning leads the proxy by 4.36 minutes. This is a positive partial-sensor/domain diagnostic against a proxy outcome. Across the three records only one minute lies outside the 30-minute target window, so zero counted false episodes cannot establish a controlled daily false-alarm rate. It is not equivalent full-input AIT generalization or new independent confirmation.','',
        '## Synthetic forecast availability delay','',
        'These are shifted forecasts, not measured IDS receipt latency. Calibration and thresholds are frozen.','',
        '| Selected blend at 15 min | Timely new warnings / 8 | False episodes | Median timely lead (min) |',
        '|---|---:|---:|---:|']
    for delay in [0,1,2,5]:
        r=get(MODES[2],15,1,FULL,delay);lead='—' if r['median_strict_lead'] is None else f"{r['median_strict_lead']:.2f}"
        lines.append(f"| {delay} min added delay | {r['strict_warned']} | {r['false_episodes']} | {lead} |")
    lines+=['','Shifting an episode start later can move it inside the strict forecast window and increase counted timely coverage. That boundary effect is not improved information or evidence that extra detector latency is beneficial.','']
    lines+=['','## Decision Network: same assumed settings','',
        '| Model | Lower assumed cost settings / 27 | Higher assumed cost settings / 27 | Mean assumed improvement |',
        '|---|---:|---:|---:|']
    utility=[]
    for mode in MODES:
        group=[r for r in decisions if r['mode']==mode and r['available']==FULL]
        by_setting=defaultdict(list)
        for r in group:by_setting[(r['damage'],r['effect_scale'],r['disruption_scale'])].append(r['improvement'])
        values=[float(np.mean(v)) for v in by_setting.values()]
        item={'mode':mode,'improved_settings':sum(v>1e-12 for v in values),
            'worse_settings':sum(v<-1e-12 for v in values),'mean_assumed_improvement':float(np.mean(values))}
        utility.append(item)
        lines.append(f"| {LABELS[mode]} | {item['improved_settings']} | {item['worse_settings']} | {item['mean_assumed_improvement']:.7g} |")
    (OUT/'decision_summary.json').write_text(json.dumps(utility,indent=2),encoding='utf-8')
    lines+=['',
        'Positive values favor delay-aware action selection over ignoring delay for the same forecast. These framewise costs use assumed efficacy and disruption, not actual intervention outcomes. A favorable utility rescore cannot establish attack prevention.','',
        '### Separately alarm-conditioned response policy','',
        'The second revision restricts non-Monitor actions to an active selected 30-minute alarm at budget 1. The delay-aware and delay-ignoring policies use the same gate and preserved probabilities. This changes the action policy, so it is a separate experiment from the preceding unrestricted framewise cost analysis.','']
    grouped=defaultdict(list)
    for r in gate_decisions:
        if r['available']==FULL:grouped[(r['damage'],r['effect_scale'],r['disruption_scale'])].append(r['improvement'])
    values=[float(np.mean(v)) for v in grouped.values()]
    gate_utility={'mode':'state_confirmed_alarm','improved_settings':sum(v>1e-12 for v in values),
        'worse_settings':sum(v<-1e-12 for v in values),'equal_settings':sum(abs(v)<=1e-12 for v in values),
        'mean_assumed_improvement':float(np.mean(values))}
    (OUT/'gate_decision_summary.json').write_text(json.dumps(gate_utility,indent=2),encoding='utf-8')
    lines += [f"Delay-aware selection has lower assumed cost in {gate_utility['improved_settings']}/27 settings, higher cost in {gate_utility['worse_settings']}/27 and ties in {gate_utility['equal_settings']}/27; mean assumed improvement is {gate_utility['mean_assumed_improvement']:.7g}. HMM confirmation is disabled by validation, so any benefit here belongs to the gated counts-only Decision Network policy. The unrestricted state-augmented policies worsen cost in 21/27 settings. Neither experiment measures actual action efficacy, avoided compromise or observed disruption.",'',
        '## What the revised evidence resolves and what remains','',
        'The implementation resolves the distinction between unavailable inputs and observed zeros, supplies genuine causal BN/HMM information to the predictor, audits fitting-stage leakage and provides an explicit no-sensor abstention. The numerical tables determine whether probability error, ranking and timely warnings improve; different metrics or operating policies may still disagree. A zero selected state weight and any worse augmented-model results remain visible.','',
        'The experiment cannot remove the limited number and relatedness of AIT campaigns, prior inspection of all outcomes, forensic detector availability, absence of successful CAM endpoint evidence, lack of long external no-target records, assumed response effects or unmatched complete published systems. Replaying the same records or tuning them again does not create fresh evidence. The existing two DARPA raw-archive cases remain limited supporting evidence; they were not relabeled as independent privilege-escalation campaigns.','',
        'The potential paper contribution remains a carefully bounded empirical finding about early warning before a later harmful stage. The revised state-feature/availability pipeline uses established techniques; better scores do not by themselves establish first-ever architecture or publication acceptance. Report positive and negative results and freeze the pipeline before fresh full-input independent evaluation.','',
        '## Reproduction and verification','',
        'Run `backend/research/run_robust_forecasting.ps1` from the workspace root. It executes the primary variants, temporal controls, same-setting utility rescore, probability-preserving alarm revision, independent verifier and report scripts. The downloaded source data and earlier original comparison predictions are prerequisites. This run does not fetch data or install software.','',
        f"Passed {verification['regression_tests']} regression tests; independently checked {verification['forecast_folds']} forecast folds, {verification['validation_thresholds']} validation thresholds, {verification['endpoint_budget_delay_rows']} endpoint/budget/delay rows, {verification['decision_settings']} assumed utility settings and {verification['external_diagnostic_rows']} external rows. Thirty-two unchanged base fits reproduce earlier raw probabilities within 1e-10. Hashes are in `reproducibility.json`.",
        '',f"Also independently checked {verification['context_control_folds']} temporal-control folds and {verification['context_test_rows']} control score rows, {verification['gate_test_rows']} revised alarm rows, {verification['gate_policy_settings']} alarm-conditioned assumed decision settings and {verification['gate_external_rows']} revised external rows.",
        '', 'Implementation references: [probability calibration](https://scikit-learn.org/stable/modules/calibration.html); [AIT source dataset](https://zenodo.org/records/5789064); [CAM source dataset](https://zenodo.org/records/18390561). Prior-system scope remains documented in `docs/NOVELTY_AUDIT.md`.','']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    labels=['Boosting','Old fusion','State + tree','Selected blend']
    for ax,h in zip(axes,[15,30]):
        rows=[old_get('temporal_boosting',h),old_get('conditional_fusion',h),get(MODES[1],h),get(MODES[2],h)]
        ax.bar(labels,[r['mean_brier']*1000 for r in rows],color=['#4878a8','#b5a07d','#71a786','#cf824b'])
        ax.set(title=f'{h}-minute observed-root endpoint',ylabel='Brier × 1000 (lower is better)')
        ax.tick_params(axis='x',rotation=15)
        for i,r in enumerate(rows):ax.text(i,r['mean_brier']*1000,f"{r['strict_warned']}/8 new; {r['false_episodes']} false",ha='center',va='bottom',fontsize=7)
        ax.margins(y=.2)
    fig.suptitle('Fixed variants and equal strict validation alarm budgets')
    fig.tight_layout();directory=OUT/'figures';directory.mkdir(exist_ok=True)
    fig.savefig(directory/'revised_probability_warning_tradeoff.png',dpi=180)
    fig.savefig(directory/'revised_probability_warning_tradeoff.pdf');plt.close(fig)
    paths=list(OUT.rglob('*'))+list((pilot.ROOT/'backend/research').glob('*.py'))+list((pilot.ROOT/'backend/tests').glob('*.py'))
    paths+=list((pilot.ROOT/'docs').glob('*.md'))+[pilot.ROOT/'experiments/robust_forecasting_protocol.md',pilot.ROOT/'experiments/separated_alarm_protocol.md',pilot.ROOT/'backend/research/run_robust_forecasting.ps1']
    paths+=list((pilot.ROOT/'data/research/extended').glob('ait_*_v2.npz'))
    paths+=[VALIDATION/'endpoint_evidence.json',COMPARISON/'budget_summary.json',study.OUT/'ait_sensor_stress.json']
    manifest={'utc':datetime.now(timezone.utc).isoformat(),
        'protocol':'experiments/robust_forecasting_protocol.md','status':'exploratory; costs assumed; no new independent campaigns',
        'sha256':{str(p.relative_to(pilot.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
            if p.is_file() and p.name!='reproducibility.json' and '__pycache__' not in p.parts}}
    (OUT/'reproducibility.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Generated revised comparison report, summary CSV/JSON, paired differences, utility summary, PNG/PDF and hash manifest',flush=True)
    for h in [15,30]:
        for mode in MODES:print(json.dumps(get(mode,h)),flush=True)

if __name__=='__main__':run()

"""Generate a better/worse assessment, including source-comparison limitations."""
import csv
import hashlib
import json
from datetime import datetime,timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import evidence_pilot as pilot
from audit_endpoints import OUT as VALIDATION
from competitive_gru import OUT,MODE
from comparison_audit import BUDGETS,HORIZONS

LABELS={'temporal_boosting':'Multi-sensor boosting','conditional_fusion':'BN/HMM + boosting fusion',
    'equal_fusion':'Equal averaging','single_aminer_boosting':'AMiner-only boosting',
    'aminer_boosting':'AMiner-only boosting','ansari2022_adapted_gru':'Original bounded GRU',
    MODE:'Validation-selected longer GRU','perera2016_adapted_filtered':'Adapted clustered HMM (filtered)',
    'duration_hmm':'Duration HMM'}

def name(mode):return LABELS.get(mode,mode)

def write_table(lines,rows):
    lines+=['| Method | Mean Brier (lower better) | Mean AP (higher better) | New warnings / 8 | False episodes | Median lead (min) |',
        '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lead='—' if r['median_strict_lead'] is None else f"{r['median_strict_lead']:.2f}"
        lines.append(f"| {name(r['mode'])} | {r['mean_brier']:.7f} | {r['mean_ap']:.4f} | {r['strict_warned']} | {r['false_episodes']} | {lead} |")

def run():
    original=json.loads((OUT/'original_threshold_summary.json').read_text())
    budgets=json.loads((OUT/'budget_summary.json').read_text())
    per_case=json.loads((OUT/'budget_fold_results.json').read_text())
    metadata=json.loads((OUT/'gru_metadata.json').read_text())
    verification=json.loads((OUT/'verification.json').read_text());assert verification['passed']
    assert all(r['campaigns']==8 for r in original+budgets)
    with (OUT/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(original[0]));writer.writeheader();writer.writerows(original)
    with (OUT/'budget_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(budgets[0]));writer.writeheader();writer.writerows(budgets)
    pick=lambda m,h:next(r for r in original if (r['mode'],r['horizon'],r['endpoint'])==(m,h,'successful_root'))
    b15=pick('temporal_boosting',15);f15=pick('conditional_fusion',15)
    b30=pick('temporal_boosting',30);f30=pick('conditional_fusion',30)
    brier_worse15=(f15['mean_brier']/b15['mean_brier']-1)*100
    brier_worse30=(f30['mean_brier']/b30['mean_brier']-1)*100
    lines=['# What improves, what worsens, and what the project can claim','',
        'The completed comparisons show useful, conditional improvements and material failures. They do not establish superiority over complete published systems or guaranteed publication. Results are exploratory: all eight AIT campaigns had already been inspected.','',
        '## What was actually done','',
        '- Inspected full primary manuscripts for HMM and GRU alert forecasting, a recent probabilistic early-warning preprint and a geo-temporal forecasting paper.',
        '- Downloaded 11 limited author files, including their Apache-2.0 license, pinned to PARD-SSM commit `ae7fb258f4795d704d8fc4fb76eb253522bd5753`; verified SHA-256 and executed the unmodified filter/fit on synthetic audit inputs. This is an implementation audit, not an AIT performance reproduction.',
        '- Trained eight additional GRU folds for 18 epochs each, selecting checkpoint 6/12/18 using validation AP only. The GRU receives the current/5/15/60-minute summaries used by boosting, in 30-minute sequences; its total temporal access is therefore longer. No test forecasts were evaluated during checkpoint selection.',
        '- Re-selected thresholds on validation campaigns using timely episode starts and four alarm budgets; independently verified 1,920 test rows, 960 validation threshold selections and 480 original-threshold comparisons across 15 model variants.',
        '- Retained the previous raw-archive DARPA experiments, endpoint proof, sensor removal, external transfer and decision sensitivity results. Corrected the CAM sensor description: Suricata is present through Wazuh; AMiner is absent.','',
        '## Main pipeline versus its strongest simpler component','',
        'These tables use the observed successful-root endpoint and the original frozen alarm thresholds. Models were trained for scheduled escalation; this is an endpoint rescore, not newly fitted root forecasting. A timely warning must begin within the horizon. Brier measures probability error; AP measures ranking; warning coverage measures cases alerted before the target. They answer different questions.','',
        '### 15-minute forecast','']
    order=['temporal_boosting','conditional_fusion','equal_fusion',MODE,
        'ansari2022_adapted_gru','perera2016_adapted_filtered','duration_hmm']
    write_table(lines,[pick(m,15) for m in order])
    lines+=['','### 30-minute forecast',''];write_table(lines,[pick(m,30) for m in order])
    lines+=['',
        f"At 30 minutes the main fusion gives {f30['strict_warned']}/8 new warnings versus {b30['strict_warned']}/8 for boosting, and {f30['false_episodes']} versus {b30['false_episodes']} false episodes. That is a 75% aggregate false-episode reduction under the original operating rule. Its Brier is **{brier_worse30:.1f}% worse**, and AP is lower. At 15 minutes Brier is **{brier_worse15:.1f}% worse**. Fewer alarms do not imply better probability forecasts.",
        '', 'The 30-minute aggregate advantage depends on wheeler: removing that campaign leaves three false episodes for boosting and four for fusion under original thresholds. This prevents a consistent across-campaign superiority claim. Root-event lead is about 19.9 minutes for fusion among the four warned cases; it is not a guarantee or an all-case average.','',
        '## Does the gain survive different alarm policies?','',
        'Thresholds below were selected using scheduled-endpoint validation data, then frozen and tested against successful-root endpoints. Budgets are false episodes per 24 negative hours on validation, with at most five negative warning minutes. Test alarm budgets are not guaranteed. The target is an impending escalation; other attacks can occur during negative exposure.','',
        '| Horizon | Validation alarm budget / 24h | Boosting new / false | Fusion new / false |',
        '|---|---:|---:|---:|']
    for h in HORIZONS:
        for budget in BUDGETS:
            lookup=lambda m:next(r for r in budgets if (r['mode'],r['endpoint'],r['horizon'],r['budget'])==(m,'successful_root',h,budget))
            b,f=lookup('temporal_boosting'),lookup('conditional_fusion')
            lines.append(f"| {h} min | {budget:g} | {b['strict_warned']} / {b['false_episodes']} | {f['strict_warned']} / {f['false_episodes']} |")
    lines+=['',
        'The low-budget 30-minute comparison is a counterexample to a universal fusion advantage: boosting warns on 4/8 cases and fusion on 3/8, with two false episodes each. At budget 1, fusion retains 4/8 with four false episodes versus 19 for boosting; removing wheeler reverses this false-episode advantage again (see per-campaign results). At 15 minutes and budget 0.25, both warn on 4/8, with one false episode for fusion versus two for boosting. The operational gain depends on both campaign and alarm policy.','',
        '## Stronger GRU comparison','',
        'The additional model uses three 32-unit layers, 18 epochs, the previous deterministic fitting-bin sample and Adam/BCE configuration, and a validation-selected checkpoint. The same validation campaign is reused for calibration and threshold selection; this is a bounded sensitivity analysis with selection bias risk, not a fully optimized neural baseline.','',
        '| Held-out campaign | Selected epoch |', '|---|---:|']
    lines += [f"| {r['test']} | {r['selected_epoch']} |" for r in metadata]
    lines+=['',
        'The numerical tables show whether the longer GRU changes the ordering. These are same-task adaptations, not reproductions of the complete Ansari paper: the author manuscript uses next Warden alert tuples, 512 GRU units, a substantially longer training budget and a different target/loss. Defeating this implementation does not establish that the published model is worse.','',
        'A secondary five-minute result also limits superiority claims: the longer GRU has mean scheduled-endpoint AP 0.6263, higher than boosting (0.3049) and fusion (0.3749). Its Brier is worse (0.0024372 versus 0.0008515 and 0.0008147), and all three start timely warnings in 0/8 cases under their original thresholds. Better ranking alone does not establish useful early alarms. These five-minute scores were independently recomputed from saved predictions; checkpoint selection used only the 15/30-minute validation AP.','',
        '## Other established gains and losses','',
        '| Comparison | Observed result | Impact on the project |', '|---|---|---|',
        '| Multi-sensor versus AMiner-only boosting, scheduled endpoint, 15 min | Mean Brier 0.0010978 versus 0.0015760: 30.3% lower; any-warning coverage 5/8 versus 2/8; three false episodes each | Supports combining sensor histories at this horizon. This gain belongs to the multi-sensor boosting component, not automatically to the full BN/HMM fusion. |',
        '| Five-minute forecasting | AMiner alone has better AP and higher any-warning coverage than full boosting or fusion | Broad claims across horizons are unsupported. |',
        '| Missing sensors | Removing AMiner or Wazuh eliminates warnings in the existing AIT removal experiment | Detector availability is a deployment dependency. |',
        '| Untouched CAM transfer, 15 min | All four frozen methods warn on 0/3 eligible tactic proxies; AMiner missing, Suricata present | Generalization is not demonstrated; targets and short exposure also prevent pooling this diagnostic with AIT. |',
        '| Decision Network sensitivity | Lower assumed cost in 11/27 settings, higher in 16/27; negative average gain | Covers Unit 3, but cannot support claims of improved prevention or real response utility. |',
        '| Duration HMM on two DARPA archives | About 9.8% lower average Brier versus geometric HMM; improvement in one case and deterioration in the other | Limited supporting evidence for duration modeling, not reliable superiority or successful DoS prediction. |','',
        '## Can we fairly say we beat other papers?','',
        '| Primary work | Checked task / artifacts | Comparable evidence here |', '|---|---|---|',
        '| [Perera et al., 2016](https://arxiv.org/html/1610.07276) | Clustered alert observations and next-alert prediction | Our clustered HMM adaptation is weaker on this common first-onset task. It changes input features and adds an onset adapter; original next-alert accuracy is not comparable. |',
        '| [Ansari et al., 2022 author manuscript](https://www.researchgate.net/publication/355133237_GRU-based_deep_learning_approach_for_network_intrusion_alert_prediction) | Next Warden alert tuples; full author manuscript inspected | Two documented bounded GRU implementations now tested on our first-onset task. Neither is a full optimized author-system reproduction. |',
        '| [PARD-SSM, 2026 preprint](https://arxiv.org/html/2604.02299v1), [author repository](https://github.com/prakulhiremath/PARD-in-Network-Traffic-using-Switching-State-Space-Models-) | Regime filtering; paper reports predictive alerts | Unmodified filtered probabilities pass a causal-prefix check (max error 0.0). The reviewed experiment fits scaler/PCA separately on test, uses its first window, evaluates retrospective Viterbi for current-state labels and lacks the complete published first-onset/KL alert evaluation. Its fit leaves A/C/Q/R unchanged. Source limitations prevent a faithful predictive comparison; no AIT superiority score is manufactured. |',
        '| [GeoGuard-PTI, 2026](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1850560/full) | Geo-temporal forecasting with synthetic propagation augmentation and simulated defense | Geo graph inputs and processed propagation traces are unavailable here. The availability statement links the generic Kaggle catalog, without an identified matching implementation/processed trace package. Its accuracy and simulation benefit cannot rank our audited campaign-onset forecasts. |','',
        'The literature check establishes existing work on predictive warnings and forecast-driven defense. It does not establish that this exact combination is unique. Missing compatible artifacts are unresolved comparisons, not evidence that a paper lacks a method or performs worse.','',
        '## Manuscript consequence','',
        'The defensible contribution is an **exploratory, endpoint-audited empirical study of multi-sensor warning forecasts and the tradeoff between alarm burden and probability quality**. State the 15-minute sensor-integration gain separately from the fusion alarm-policy tradeoff. Report the reversed campaign result, low-budget lost coverage, external misses and negative response sensitivity. Do not claim a new inference algorithm, universally better early warning, prevention efficacy or state of the art.','',
        'Unit 1 remains Bayesian inference/count likelihood and conditional fusion; Unit 2 remains HMM filtering/duration/onset projection; Unit 3 remains the Decision Network with action-delay utility. A substantial syllabus component can remain useful even when its empirical ablation is negative.','',
        'The next evidence needed for a stronger generalization paper is independently generated campaigns with complete detector inputs, verified successful endpoints and measured online availability, evaluated under a frozen model-selection/threshold protocol. An empirical improvement supports a research contribution; acceptance and first-ever novelty are not established by a percentage gain.','',
        '## Reproduce and inspect','',
        'Run `python backend/research/competitive_gru.py`, then `comparison_audit.py`, `verify_comparison.py` and `report_comparison.py` from the workspace root. Existing original caches/predictions and the pinned author snapshot are prerequisites. No new packages are required beyond the previous research environment.','',
        f"Verification passed: {verification['gru_folds']} new GRU folds, {verification['budget_test_rows']} budget test rows, {verification['validation_thresholds']} validation selections and {verification['original_threshold_rows']} original-threshold rescores. JSON/CSV outputs and the protocol retain per-campaign results. Source and artifact hashes are in `reproducibility.json`. The native author audit executed on synthetic inputs only; it is not a published-system performance reproduction.",'']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    fig,axes=plt.subplots(1,2,figsize=(9,3.5))
    for ax,h in zip(axes,HORIZONS):
        for mode,color in [('temporal_boosting','#4878a8'),('conditional_fusion','#cf824b')]:
            group=sorted([r for r in budgets if (r['mode'],r['endpoint'],r['horizon'])==(mode,'successful_root',h)],key=lambda r:r['budget'])
            ax.plot([r['false_episodes'] for r in group],[r['strict_warned'] for r in group],'-o',label=name(mode),color=color)
            locations={}
            for r in group:
                locations.setdefault((r['false_episodes'],r['strict_warned']),[]).append(r['budget'])
            for point,values in locations.items():
                label='b='+','.join(f'{v:g}' for v in values)
                offset=(6,10) if mode=='temporal_boosting' else (6,-18)
                ax.annotate(label,point,xytext=offset,textcoords='offset points',fontsize=8,color=color)
        ax.set(title=f'{h}-minute root warnings',xlabel='Test false episodes',ylabel='Timely new warnings / 8',ylim=(0,8.5))
        ax.grid(alpha=.2);ax.legend(fontsize=8);ax.margins(x=.25)
    fig.suptitle('Validation-selected alarm budgets: fusion advantage depends on policy')
    fig.tight_layout();directory=OUT/'figures';directory.mkdir(exist_ok=True)
    fig.savefig(directory/'alarm_policy_tradeoff.png',dpi=180);fig.savefig(directory/'alarm_policy_tradeoff.pdf');plt.close(fig)
    paths=list(OUT.rglob('*'))+[pilot.ROOT/'experiments/published_comparison_protocol.md']
    paths+=list((pilot.ROOT/'backend/research').glob('*.py'))+list((pilot.ROOT/'backend/tests').glob('*.py'))
    paths+=list((pilot.ROOT/'third_party/pard_ssm').rglob('*'))
    paths+=list((pilot.ROOT/'docs').glob('*.md'))
    paths+=list((VALIDATION/'predictions').glob('ait_*.npz'))+list((VALIDATION).glob('*.json'))
    original_directory=pilot.ROOT/'experiments/extended_study'
    paths+=list((original_directory/'predictions').glob('ait_*.npz'))+list(original_directory.glob('*fold_results.json'))
    paths+=list((pilot.ROOT/'data/research/extended').glob('ait_*_v2.npz'))
    manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),
        'sha256':{str(p.relative_to(pilot.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
            if p.is_file() and p.name!='reproducibility.json' and '__pycache__' not in p.parts},
        'status':'exploratory; full published-system superiority unestablished'}
    (OUT/'reproducibility.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Generated comparison report, CSV tables, PNG/PDF policy figure and hash manifest',flush=True)

if __name__=='__main__':run()

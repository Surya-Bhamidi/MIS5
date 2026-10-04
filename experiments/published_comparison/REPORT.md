# What improves, what worsens, and what the project can claim

The completed comparisons show useful, conditional improvements and material failures. They do not establish superiority over complete published systems or guaranteed publication. Results are exploratory: all eight AIT campaigns had already been inspected.

## What was actually done

- Inspected full primary manuscripts for HMM and GRU alert forecasting, a recent probabilistic early-warning preprint and a geo-temporal forecasting paper.
- Downloaded 11 limited author files, including their Apache-2.0 license, pinned to PARD-SSM commit `ae7fb258f4795d704d8fc4fb76eb253522bd5753`; verified SHA-256 and executed the unmodified filter/fit on synthetic audit inputs. This is an implementation audit, not an AIT performance reproduction.
- Trained eight additional GRU folds for 18 epochs each, selecting checkpoint 6/12/18 using validation AP only. The GRU receives the current/5/15/60-minute summaries used by boosting, in 30-minute sequences; its total temporal access is therefore longer. No test forecasts were evaluated during checkpoint selection.
- Re-selected thresholds on validation campaigns using timely episode starts and four alarm budgets; independently verified 1,920 test rows, 960 validation threshold selections and 480 original-threshold comparisons across 15 model variants.
- Retained the previous raw-archive DARPA experiments, endpoint proof, sensor removal, external transfer and decision sensitivity results. Corrected the CAM sensor description: Suricata is present through Wazuh; AMiner is absent.

## Main pipeline versus its strongest simpler component

These tables use the observed successful-root endpoint and the original frozen alarm thresholds. Models were trained for scheduled escalation; this is an endpoint rescore, not newly fitted root forecasting. A timely warning must begin within the horizon. Brier measures probability error; AP measures ranking; warning coverage measures cases alerted before the target. They answer different questions.

### 15-minute forecast

| Method | Mean Brier (lower better) | Mean AP (higher better) | New warnings / 8 | False episodes | Median lead (min) |
|---|---:|---:|---:|---:|---:|
| Multi-sensor boosting | 0.0011185 | 0.7177 | 4 | 3 | 11.19 |
| BN/HMM + boosting fusion | 0.0016302 | 0.6830 | 4 | 2 | 10.57 |
| Equal averaging | 0.0039323 | 0.5502 | 1 | 3 | 6.08 |
| Validation-selected longer GRU | 0.0044173 | 0.4301 | 1 | 8 | 3.66 |
| Original bounded GRU | 0.0026363 | 0.0409 | 0 | 0 | — |
| Adapted clustered HMM (filtered) | 0.0025680 | 0.0161 | 0 | 0 | — |
| Duration HMM | 0.0027635 | 0.0912 | 0 | 0 | — |

### 30-minute forecast

| Method | Mean Brier (lower better) | Mean AP (higher better) | New warnings / 8 | False episodes | Median lead (min) |
|---|---:|---:|---:|---:|---:|
| Multi-sensor boosting | 0.0015254 | 0.8320 | 4 | 20 | 20.90 |
| BN/HMM + boosting fusion | 0.0019966 | 0.7705 | 4 | 5 | 19.87 |
| Equal averaging | 0.0047535 | 0.6755 | 3 | 3 | 19.66 |
| Validation-selected longer GRU | 0.0068378 | 0.3607 | 4 | 16 | 19.60 |
| Original bounded GRU | 0.0056637 | 0.1552 | 0 | 2 | — |
| Adapted clustered HMM (filtered) | 0.0051208 | 0.0179 | 0 | 0 | — |
| Duration HMM | 0.0085230 | 0.1906 | 2 | 40 | 21.07 |

At 30 minutes the main fusion gives 4/8 new warnings versus 4/8 for boosting, and 5 versus 20 false episodes. That is a 75% aggregate false-episode reduction under the original operating rule. Its Brier is **30.9% worse**, and AP is lower. At 15 minutes Brier is **45.7% worse**. Fewer alarms do not imply better probability forecasts.

The 30-minute aggregate advantage depends on wheeler: removing that campaign leaves three false episodes for boosting and four for fusion under original thresholds. This prevents a consistent across-campaign superiority claim. Root-event lead is about 19.9 minutes for fusion among the four warned cases; it is not a guarantee or an all-case average.

## Does the gain survive different alarm policies?

Thresholds below were selected using scheduled-endpoint validation data, then frozen and tested against successful-root endpoints. Budgets are false episodes per 24 negative hours on validation, with at most five negative warning minutes. Test alarm budgets are not guaranteed. The target is an impending escalation; other attacks can occur during negative exposure.

| Horizon | Validation alarm budget / 24h | Boosting new / false | Fusion new / false |
|---|---:|---:|---:|
| 15 min | 0 | 3 / 2 | 2 / 1 |
| 15 min | 0.25 | 4 / 2 | 4 / 1 |
| 15 min | 1 | 4 / 3 | 4 / 2 |
| 15 min | 4 | 4 / 3 | 4 / 2 |
| 30 min | 0 | 4 / 2 | 3 / 2 |
| 30 min | 0.25 | 4 / 2 | 3 / 2 |
| 30 min | 1 | 4 / 19 | 4 / 4 |
| 30 min | 4 | 4 / 19 | 4 / 4 |

The low-budget 30-minute comparison is a counterexample to a universal fusion advantage: boosting warns on 4/8 cases and fusion on 3/8, with two false episodes each. At budget 1, fusion retains 4/8 with four false episodes versus 19 for boosting; removing wheeler reverses this false-episode advantage again (see per-campaign results). At 15 minutes and budget 0.25, both warn on 4/8, with one false episode for fusion versus two for boosting. The operational gain depends on both campaign and alarm policy.

## Stronger GRU comparison

The additional model uses three 32-unit layers, 18 epochs, the previous deterministic fitting-bin sample and Adam/BCE configuration, and a validation-selected checkpoint. The same validation campaign is reused for calibration and threshold selection; this is a bounded sensitivity analysis with selection bias risk, not a fully optimized neural baseline.

| Held-out campaign | Selected epoch |
|---|---:|
| fox | 12 |
| harrison | 6 |
| russellmitchell | 6 |
| santos | 6 |
| shaw | 12 |
| wardbeck | 12 |
| wheeler | 6 |
| wilson | 18 |

The numerical tables show whether the longer GRU changes the ordering. These are same-task adaptations, not reproductions of the complete Ansari paper: the author manuscript uses next Warden alert tuples, 512 GRU units, a substantially longer training budget and a different target/loss. Defeating this implementation does not establish that the published model is worse.

A secondary five-minute result also limits superiority claims: the longer GRU has mean scheduled-endpoint AP 0.6263, higher than boosting (0.3049) and fusion (0.3749). Its Brier is worse (0.0024372 versus 0.0008515 and 0.0008147), and all three start timely warnings in 0/8 cases under their original thresholds. Better ranking alone does not establish useful early alarms. These five-minute scores were independently recomputed from saved predictions; checkpoint selection used only the 15/30-minute validation AP.

## Other established gains and losses

| Comparison | Observed result | Impact on the project |
|---|---|---|
| Multi-sensor versus AMiner-only boosting, scheduled endpoint, 15 min | Mean Brier 0.0010978 versus 0.0015760: 30.3% lower; any-warning coverage 5/8 versus 2/8; three false episodes each | Supports combining sensor histories at this horizon. This gain belongs to the multi-sensor boosting component, not automatically to the full BN/HMM fusion. |
| Five-minute forecasting | AMiner alone has better AP and higher any-warning coverage than full boosting or fusion | Broad claims across horizons are unsupported. |
| Missing sensors | Removing AMiner or Wazuh eliminates warnings in the existing AIT removal experiment | Detector availability is a deployment dependency. |
| Untouched CAM transfer, 15 min | All four frozen methods warn on 0/3 eligible tactic proxies; AMiner missing, Suricata present | Generalization is not demonstrated; targets and short exposure also prevent pooling this diagnostic with AIT. |
| Decision Network sensitivity | Lower assumed cost in 11/27 settings, higher in 16/27; negative average gain | Covers Unit 3, but cannot support claims of improved prevention or real response utility. |
| Duration HMM on two DARPA archives | About 9.8% lower average Brier versus geometric HMM; improvement in one case and deterioration in the other | Limited supporting evidence for duration modeling, not reliable superiority or successful DoS prediction. |

## Can we fairly say we beat other papers?

| Primary work | Checked task / artifacts | Comparable evidence here |
|---|---|---|
| [Perera et al., 2016](https://arxiv.org/html/1610.07276) | Clustered alert observations and next-alert prediction | Our clustered HMM adaptation is weaker on this common first-onset task. It changes input features and adds an onset adapter; original next-alert accuracy is not comparable. |
| [Ansari et al., 2022 author manuscript](https://www.researchgate.net/publication/355133237_GRU-based_deep_learning_approach_for_network_intrusion_alert_prediction) | Next Warden alert tuples; full author manuscript inspected | Two documented bounded GRU implementations now tested on our first-onset task. Neither is a full optimized author-system reproduction. |
| [PARD-SSM, 2026 preprint](https://arxiv.org/html/2604.02299v1), [author repository](https://github.com/prakulhiremath/PARD-in-Network-Traffic-using-Switching-State-Space-Models-) | Regime filtering; paper reports predictive alerts | Unmodified filtered probabilities pass a causal-prefix check (max error 0.0). The reviewed experiment fits scaler/PCA separately on test, uses its first window, evaluates retrospective Viterbi for current-state labels and lacks the complete published first-onset/KL alert evaluation. Its fit leaves A/C/Q/R unchanged. Source limitations prevent a faithful predictive comparison; no AIT superiority score is manufactured. |
| [GeoGuard-PTI, 2026](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1850560/full) | Geo-temporal forecasting with synthetic propagation augmentation and simulated defense | Geo graph inputs and processed propagation traces are unavailable here. The availability statement links the generic Kaggle catalog, without an identified matching implementation/processed trace package. Its accuracy and simulation benefit cannot rank our audited campaign-onset forecasts. |

The literature check establishes existing work on predictive warnings and forecast-driven defense. It does not establish that this exact combination is unique. Missing compatible artifacts are unresolved comparisons, not evidence that a paper lacks a method or performs worse.

## Manuscript consequence

The defensible contribution is an **exploratory, endpoint-audited empirical study of multi-sensor warning forecasts and the tradeoff between alarm burden and probability quality**. State the 15-minute sensor-integration gain separately from the fusion alarm-policy tradeoff. Report the reversed campaign result, low-budget lost coverage, external misses and negative response sensitivity. Do not claim a new inference algorithm, universally better early warning, prevention efficacy or state of the art.

Unit 1 remains Bayesian inference/count likelihood and conditional fusion; Unit 2 remains HMM filtering/duration/onset projection; Unit 3 remains the Decision Network with action-delay utility. A substantial syllabus component can remain useful even when its empirical ablation is negative.

The next evidence needed for a stronger generalization paper is independently generated campaigns with complete detector inputs, verified successful endpoints and measured online availability, evaluated under a frozen model-selection/threshold protocol. An empirical improvement supports a research contribution; acceptance and first-ever novelty are not established by a percentage gain.

## Reproduce and inspect

Run `python backend/research/competitive_gru.py`, then `comparison_audit.py`, `verify_comparison.py` and `report_comparison.py` from the workspace root. Existing original caches/predictions and the pinned author snapshot are prerequisites. No new packages are required beyond the previous research environment.

Verification passed: 8 new GRU folds, 1920 budget test rows, 960 validation selections and 480 original-threshold rescores. JSON/CSV outputs and the protocol retain per-campaign results. Source and artifact hashes are in `reproducibility.json`. The native author audit executed on synthetic inputs only; it is not a published-system performance reproduction.

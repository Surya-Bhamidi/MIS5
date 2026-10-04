# Publication validation report

**Current research version:** fixed .25 BN/HMM state fusion, with 30-minute warning as its primary use case. Further advancements are deferred. See [the preset specification](../../docs/CURRENT_VERSION.md) and [frozen artifacts](../current_version/README.md). This post-result development choice preserves every earlier comparison and does not establish a universally best model.

**Latest completed analysis:** [selective fusion with campaign-based calibration](../selective_fusion/REPORT.md) has passed 33 tests and independent score/selection checks. A prespecified .25 state blend gives 5/8 timely 30-minute root warnings versus 4/8 for original counts-only, 4.25% lower Brier and five versus 19 false episodes overall. The false-episode gain reverses when wheeler is removed. The adaptive selector produces 5/8 15-minute warnings but 17 false episodes, so its primary target fails. Missing-Wazuh selective fusion has a conditional gain against matched pooled counts. No overall superiority or independent generalization is established.

**Previous improvement analysis:** [revised availability and BN/HMM experiments](../robust_forecasting/REPORT.md) tested state features and confirmation. Availability-specific counts recovered 3/8 timely warnings with Wazuh missing, but full-input state augmentation worsened 15-minute coverage and probability error. The confirmation revision selected no HMM confirmation at the primary horizons. The frozen original results below remain unchanged.

This extends the completed exploratory study. It makes the evidence more auditable; it does not establish first-ever architecture, state of the art, or guaranteed publication. Existing predictions and thresholds were frozen for endpoint and latency rescoring. All negative results are retained.

Additional completed checks are in [the comparison report](../published_comparison/REPORT.md): eight validation-selected longer GRU folds, a pinned author-code audit and four validation-selected alarm policies across 15 model variants. At a tighter 30-minute budget, boosting gives 4/8 timely root warnings versus 3/8 for fusion at two false episodes each; at the larger budget both give 4/8 and fusion reduces false episodes from 19 to 4. This strengthens the evidence for a policy-dependent tradeoff, not full published-system superiority.

## Successful endpoint validation

Original attacker execution logs and attack-labelled victim audit records were retrieved for every AIT campaign. SHA-256 validates the local selected members, and ZIP CRC checks ran during retrieval. Only selected ZIP members were downloaded; whole archive checksums were not verified. Evaluation labels never enter count features.

| Campaign | Successful user-change offset (s) | Successful root offset (s) |
|---|---:|---:|
| fox | 2.403 | 13.331 |
| harrison | 2.052 | 20.308 |
| russellmitchell | 1.627 | 27.243 |
| santos | 1.024 | 12.056 |
| shaw | 1.800 | 14.836 |
| wardbeck | 1.359 | 15.995 |
| wheeler | 0.779 | 18.343 |
| wilson | 1.014 | 21.654 |

Offsets are relative to the published scheduled escalation. A successful USER_START session for `/bin/su` confirms the change from web-service identity to a system user. A later attack-labelled `/usr/bin/sudo` USER_START session with account root is the distinct root endpoint. The root rescore retains models trained for the original scheduled endpoint; it is an endpoint sensitivity analysis, not a newly fitted root predictor.

The earlier DNSteal ordering concern is resolved by the original dataset paper: exfiltration deliberately starts at simulation beginning as a separate background attack. Negative forecast exposure therefore means no impending target event, not necessarily benign traffic.

## Same-task baseline results at 15 minutes

Each AIT fold has six fitting, one calibration/threshold and one test campaign. Scores are campaign means, not millions of independent attacks. Lower Brier is better; higher average precision is better. Timely new warnings require a warning episode to BEGIN inside the valid forecast window. Any-warning coverage also counts persistent earlier alerts and is therefore more permissive.

| Model | Mean Brier | Mean AP | Any warning / 8 | Timely new warning / 8 | False episodes |
|---|---:|---:|---:|---:|---:|
| ansari2022_adapted_gru | 0.0026355 | 0.0416 | 0 | 0 | 0 |
| boosting_current_only | 0.0026071 | 0.0049 | 0 | 0 | 0 |
| boosting_only_aminer | 0.0015760 | 0.6565 | 2 | 1 | 3 |
| boosting_only_suricata | 0.0031788 | 0.1124 | 0 | 0 | 6 |
| boosting_only_wazuh | 0.0047530 | 0.5337 | 2 | 1 | 7 |
| conditional_fusion | 0.0015798 | 0.6899 | 5 | 4 | 2 |
| detector_hmm | 0.0025888 | 0.0194 | 0 | 0 | 0 |
| duration_hmm | 0.0027625 | 0.0936 | 0 | 0 | 0 |
| equal_fusion | 0.0039322 | 0.5516 | 2 | 1 | 3 |
| perera2016_adapted_filtered | 0.0025712 | 0.0079 | 0 | 0 | 0 |
| perera2016_adapted_viterbi | 0.0025712 | 0.0065 | 0 | 0 | 0 |
| static_bn | 0.0025715 | 0.0051 | 0 | 0 | 0 |
| temporal_boosting | 0.0010978 | 0.7214 | 5 | 4 | 3 |
| temporal_logistic | 0.0024064 | 0.3359 | 2 | 1 | 8 |

The Perera2016 adaptation uses fitted count clusters, an unsupervised categorical HMM and an added target hazard. The paper instead predicts next alert clusters from per-alert bag-of-words/IP/port features. The GRU is a bounded implementation inspired by Ansari2022; it predicts first onset from minute counts instead of Warden next alerts. These are comparable implementations of adapted method families, not full published-system reproductions. Original accuracy figures must not be compared with these Brier scores.

## Observed root endpoint: operational tradeoff at 30 minutes

| Model | Mean Brier | Mean AP | Any / new warnings | False episodes | Median new-warning lead (min) |
|---|---:|---:|---:|---:|---:|
| temporal_boosting | 0.0015254 | 0.8320 | 5 / 4 | 20 | 20.90 |
| conditional_fusion | 0.0019966 | 0.7705 | 5 / 4 | 5 | 19.87 |
| equal_fusion | 0.0047535 | 0.6755 | 5 / 3 | 3 | 19.66 |

Fusion reduces the total false episodes by 75% (20 to 5) at the same 4/8 timely new-warning coverage. It worsens Brier and ranking. Removing wheeler leaves false totals 3 for boosting and 4 for learned fusion: the aggregate improvement reverses. Equal averaging has fewer false episodes than learned fusion but only 3/8 timely new warnings and worse probability error. These competing results prevent a universal improvement claim.

## Synthetic availability delay sensitivity

Forecasts were shifted by 1, 2 and 5 minutes with fixed calibration and thresholds. This tests stale information, not actual IDS receipt latency. Padding uses no forecast before one is available. At 15 minutes, learned fusion still starts timely new warnings in 4/8 root cases, but its median lead decreases as follows.

| Added delay (min) | New warnings / 8 | Median lead (min) | False episodes |
|---|---:|---:|---:|
| 0 | 4 | 10.57 | 2 |
| 1 | 4 | 9.57 | 2 |
| 2 | 4 | 8.57 | 2 |
| 5 | 4 | 5.57 | 2 |

## Untouched CAM-LDS transfer diagnostic

Six distinct templates were chosen before outcome scoring. Full Wazuh streams, rather than attack-filtered manifestations, were retrieved. Three contain a published privilege-escalation tactic and three do not. The frozen AIT fox-fold base models, fusion coefficients, harrison calibration and thresholds were reused without CAM tuning. Recomputed original validation probabilities match exactly (maximum error 0.0).

| Template | Available sensor families | Pre-proxy minutes | Eligible |
|---|---|---:|---|
| scenario_1_sudo_localaccount | wazuh, suricata | 32.0 | True |
| scenario_2_cron | wazuh, suricata | 0.0 | False |
| scenario_3_ssh_apt | wazuh, suricata | 13.8 | True |
| scenario_4 | wazuh, suricata | 18.5 | True |
| scenario_5 | wazuh, suricata | 0.0 | False |
| scenario_6_macro_binary | wazuh, suricata | 0.0 | False |

At 15 minutes, duration HMM, boosting, learned fusion and equal fusion each produce **0/3 warnings** and zero false episodes. This is a negative transfer result. AMiner is absent; native Wazuh includes Suricata alerts and a different detector mix. The outcome is the first executed privilege tactic, not independently verified successful escalation. One eligible trace has no negative forecast bins at 15 minutes, so its false-alarm rate is undefined (null), not a measured zero rate. These short records cannot validate a daily alarm budget. Do not combine these cases with AIT recall or call this full-pipeline generalization.

## Decision Network and syllabus coverage

| Unit | Substantive implemented use |
|---|---|
| 1 | Bayesian threat-state parent with detector-count children; factorized observation likelihood and conditional fusion CPD |
| 2 | Forward HMM filtering, age-expanded duration states and first-onset projection |
| 3 | Onset-time chance node, response decision, delayed effectiveness and expected damage/disruption utility |

The previous 27-setting sensitivity analysis found delay-aware fusion decisions improve assumed cost in 11 settings and worsen it in 16, with negative mean improvement. Costs and effects are assumptions; no action was executed to measure prevention. Including a Decision Network does not establish improved response outcomes.

## Defensible contribution and remaining limits

The strongest scope is an endpoint-audited empirical study of multi-sensor forecasting and alarm/probability tradeoffs. The full temporal tree has 30.3% lower mean 15-minute Brier than the best single-sensor tree (AMiner), with 5/8 rather than 2/8 any-warning coverage at three false episodes for each. At five minutes, AMiner alone gives better ranking and more warnings, so the gain is horizon-dependent. The probabilistic fusion adds a conditional operational tradeoff, not a new inference algorithm.

All eight AIT campaigns were inspected during development; folds and bootstrap intervals are exploratory. The adapted HMM and fixed-budget GRU are not optimized replicas of full prior systems. Source alert generation is forensic and may have training/delivery behavior different from online IDS deployment; causal clock features alone do not prove true receipt-time availability. The legacy app and cached demonstration results remain separate from the research experiment engine.

A manuscript draft is provided in `docs/PAPER_DRAFT.md`. A strong generalized-superiority paper still needs fresh full-sensor campaigns with independently verified successful endpoints and measured availability, plus competitive validation-only tuning or faithful compatible author-code comparisons. These are concrete evidence gaps, not a promise that more tuning will improve the combination.

## Reproduction

After the original research caches and saved predictions exist, run `backend/research/run_publication_validation.ps1`. Network retrieval is opt-in via `-FetchPublicEvidence`; otherwise it uses the already downloaded selected members. Full results: `baseline_comparison.csv`, `endpoint_rescored.csv`, `cam_transfer.json`, individual forecast NPZ files and `verification.json`.

## Primary references

- [Perera Miriya Thanthrige et al., HMM alert prediction](https://arxiv.org/html/1610.07276).
- [Ansari et al., GRU alert prediction](https://research.tus.ie/en/publications/gru-based-deep-learning-approach-for-network-intrusion-alert-pred/).
- [AIT dataset paper, Sections 3.2 and 4](https://arxiv.org/pdf/2203.08580.pdf).
- [Original AIT execution/audit data](https://zenodo.org/records/5789064).
- [CAM-LDS complete scenario logs](https://zenodo.org/records/18390561).
- [Withdrawn E-HiDNet preprint; excluded from validated comparisons](https://arxiv.org/abs/2601.06734).

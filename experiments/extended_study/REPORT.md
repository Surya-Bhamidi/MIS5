# Extended research results — 4 October 2026

**Verdict: useful improvements were measured against reproduced component baselines. A universal advantage over the strongest tested baseline, originality of the combination, and superiority to complete published systems are not established.**

The tested learned combination joins a duration-aware BN-HMM forecast and a boosted-tree forecast using a conditional logistic CPD trained on inner held-out campaigns. This is conventional stacking. Equal averaging is also tested. At 30 minutes learned fusion has the same 5/8 warning coverage as boosting and 5 rather than 20 false-warning episodes; probability error and ranking worsen. Most of the false-episode reduction comes from wheeler (17 to 1), offset by more false episodes on harrison (0 to 2). Equal averaging has only three false episodes at that horizon but worse probability quality and earlier warning coverage is weaker. This is a narrow operating-point result, not general superiority.

A separate positive combination finding: at 15 minutes the three-sensor temporal tree warns on 5/8 campaigns versus 2/8 for the AMiner-only temporal tree, with three false episodes for each. Mean Brier falls from 0.001576 to 0.001098 (30.3% reduction), and AP rises from 0.6565 to 0.7214. The Wazuh-only tree also warns on 2/8, Suricata-only on 0/8, and the all-sensor current-count-only tree on 0/8. This supports the value of combining sensor histories on this task. At five minutes AMiner-only has better AP and 3/8 coverage than either the full tree or learned fusion; the gain is horizon-dependent. None of these comparisons alone establishes algorithmic originality.

## Dataset and evaluation

- AIT: all eight scenarios, rotating six fitting / one validation / one test. The target is the published scheduled privilege-escalation start, not verified compromise or DDoS. Current detector identifiers and trailing 5/15/60-minute counts are the only supervised inputs; no target labels, host identities or relative-onset time are features. AIT was inspected and evaluated in preceding pilots: this extension is exploratory reused development evidence.
- DARPA: both local tar.gz archives, full inside and DMZ PCAPs, background included; 1,628,616 packets in total. Target is the first ACK flood burst, not the phase-5 login. March uses EST and April EDT. Only two related campaigns; transfer thresholds use the fitting campaign, not independent validation. MIT states the DDoS did not actually succeed, so flood emission is the endpoint.
- A forecast at minute t uses only completed bins ending by t. Observed alert timestamp availability is assumed; actual end-to-end collection latency is not validated. Exact report identities are deduplicated. Vocabulary, bucket edges, emission/transition/duration parameters and supervised models use fitting campaigns only. Fusion coefficients use two inner three-versus-three campaign splits. Calibration and warning thresholds use the outer validation campaign.
- AIT retains the earlier pilot clock beginning at midnight before the earliest alert. Initial empty prefixes total about 4.5 hours across the eight scenarios; they are included in approximately 790 hours of negative clock exposure. Continuous telemetry coverage cannot be verified from alert-only data. Rates assume coverage on that grid, and must not be described as independently verified benign operating hours.
- Every model shares labels, clock and evaluation exposure. Warning selection constrains validation to at most one false episode per 24 negative hours and five negative warning minutes. Those limits are not guaranteed on test campaigns. An episode is false if its start lies outside the target horizon; continuous false warnings that persist into that horizon can also count toward warning coverage. Negative warning minutes reveal persistent alarms. AP is sklearn average precision, not trapezoidal PR area.
- Scores are campaign means, not pooled independent alert samples. Every horizon, raw and calibrated score, fixed threshold and negative result is released. Transformed sensor-outage traces are not additional independent campaigns.

## AIT natural traces: 15-minute forecasts

| Method | Brier ↓ | AP ↑ | Warned | False episodes | False / 24h | Negative warning min | Median lead, warned only |
|---|---:|---:|---:|---:|---:|---:|---:|
| Static BN | 0.002572 | 0.0051 | 0/8 | 0 | 0.000 | 0 | — |
| Detector BN-HMM | 0.002589 | 0.0194 | 0/8 | 0 | 0.000 | 0 | — |
| Duration BN-HMM | 0.002763 | 0.0936 | 0/8 | 0 | 0.000 | 0 | — |
| Temporal logistic | 0.002406 | 0.3359 | 2/8 | 8 | 0.243 | 38 | 13.40 min |
| Boosted-tree forecast | 0.001098 | 0.7214 | 5/8 | 3 | 0.091 | 28 | 12.30 min |
| Equal fusion | 0.003932 | 0.5516 | 2/8 | 3 | 0.091 | 28 | 10.24 min |
| Learned conditional fusion | 0.001580 | 0.6899 | 5/8 | 2 | 0.061 | 27 | 12.30 min |

## AIT natural traces: 5-minute forecasts

| Method | Brier ↓ | AP ↑ | Warned | False episodes | False / 24h | Negative warning min | Median lead, warned only |
|---|---:|---:|---:|---:|---:|---:|---:|
| Static BN | 0.000859 | 0.0033 | 0/8 | 0 | 0.000 | 0 | — |
| Detector BN-HMM | 0.000905 | 0.0063 | 0/8 | 0 | 0.000 | 0 | — |
| Duration BN-HMM | 0.001061 | 0.0168 | 0/8 | 0 | 0.000 | 0 | — |
| Temporal logistic | 0.001106 | 0.0997 | 0/8 | 0 | 0.000 | 0 | — |
| Boosted-tree forecast | 0.000851 | 0.3049 | 1/8 | 6 | 0.182 | 18 | 4.30 min |
| Equal fusion | 0.001940 | 0.1359 | 0/8 | 0 | 0.000 | 0 | — |
| Learned conditional fusion | 0.000815 | 0.3749 | 1/8 | 1 | 0.030 | 5 | 4.50 min |

## AIT natural traces: 30-minute forecasts

| Method | Brier ↓ | AP ↑ | Warned | False episodes | False / 24h | Negative warning min | Median lead, warned only |
|---|---:|---:|---:|---:|---:|---:|---:|
| Static BN | 0.005141 | 0.0093 | 0/8 | 0 | 0.000 | 0 | — |
| Detector BN-HMM | 0.008139 | 0.1168 | 2/8 | 496 | 15.101 | 625 | 15.79 min |
| Duration BN-HMM | 0.008514 | 0.2002 | 2/8 | 40 | 1.218 | 393 | 20.79 min |
| Temporal logistic | 0.004495 | 0.4209 | 3/8 | 58 | 1.766 | 182 | 27.62 min |
| Boosted-tree forecast | 0.001522 | 0.8311 | 5/8 | 20 | 0.609 | 69 | 21.50 min |
| Equal fusion | 0.004754 | 0.6732 | 5/8 | 3 | 0.091 | 11 | 19.83 min |
| Learned conditional fusion | 0.001953 | 0.7738 | 5/8 | 5 | 0.152 | 18 | 29.62 min |

## Fixed-setting feature ablations: 15-minute forecasts

Each single-sensor tree is trained on that sensor, unlike removal stress. The current-count tree omits all temporal means. These additional comparisons were declared after the initial results and remain exploratory; they do not tune or replace the candidate. All six horizons are preserved in the summary and CSV files.

| Method | Brier ↓ | AP ↑ | Warned | False episodes | False / 24h | Negative warning min | Median lead, warned only |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tree: current counts only | 0.002607 | 0.0049 | 0/8 | 0 | 0.000 | 0 | — |
| Tree: AMiner only | 0.001576 | 0.6565 | 2/8 | 3 | 0.091 | 26 | 10.24 min |
| Tree: Suricata only | 0.003179 | 0.1124 | 0/8 | 6 | 0.182 | 14 | — |
| Tree: Wazuh only | 0.004753 | 0.5337 | 2/8 | 7 | 0.213 | 39 | 10.97 min |
| Boosted-tree forecast | 0.001098 | 0.7214 | 5/8 | 3 | 0.091 | 28 | 12.30 min |

## Paired uncertainty for fusion versus boosting

Campaign bootstrap (20,000 draws, seed 1729). Positive differences favor fusion. Intervals are descriptive: only eight related scenarios, overlapping fitted models, reused test results and multiple exploratory comparisons prevent confirmatory significance claims.

| Horizon | Brier improvement [95% descriptive interval] | AP improvement [interval] | False episodes reduced per campaign [interval] |
|---|---:|---:|---:|
| 5 min | 3.68019e-05 [-9.88444e-05, 0.000177056] | 0.06997 [0.011492, 0.149706] | 0.625 [-0.25, 2] |
| 15 min | -0.000482001 [-0.00106262, 7.30254e-06] | -0.0314809 [-0.110866, 0.0336967] | 0.125 [0, 0.375] |
| 30 min | -0.000430725 [-0.0010583, -2.44484e-05] | -0.0573665 [-0.144056, 0.00261633] | 1.875 [-0.625, 6.125] |

## DARPA transfer: 15-minute forecasts

| Method | Brier ↓ | AP ↑ | Warned | False episodes | False / 24h | Negative warning min | Median lead, warned only |
|---|---:|---:|---:|---:|---:|---:|---:|
| Static BN | 0.162022 | 0.1374 | 0/2 | 0 | 0.000 | 0 | — |
| Detector BN-HMM | 0.153022 | 0.2028 | 0/2 | 1 | 8.276 | 1 | — |
| Duration BN-HMM | 0.137961 | 0.5186 | 1/2 | 6 | 49.655 | 19 | 14.85 min |
| Temporal logistic | 0.166003 | 0.1733 | 0/2 | 2 | 16.552 | 2 | — |
| Boosted-tree forecast | 0.225245 | 0.1803 | 0/2 | 0 | 0.000 | 0 | — |

The duration model improves the two-campaign mean Brier over the ordinary detector HMM, but only one of two outcomes is warned and six false episodes occur. One transfer improves and the other worsens. Very short negative exposure amplifies false-warning rates; this is not a validated operational DDoS system. Phase labels also represent different intermediate behaviors between the two DARPA variants.

## Equal-input sensor-outage stress

Each sensor is removed for the entire held-out trace. Training, calibration, thresholds and ground truth remain natural and unchanged. Missing telemetry is represented by zero counts without an explicit health flag; this measures robustness to that particular input failure.

| Removed AIT sensor | Method | 15-min Brier | AP | Warned | False episodes |
|---|---|---:|---:|---:|---:|
| aminer | Duration BN-HMM | 0.002755 | 0.0711 | 0/8 | 0 |
| aminer | Boosted-tree forecast | 0.002608 | 0.2400 | 0/8 | 1 |
| aminer | Learned conditional fusion | 0.002612 | 0.2201 | 0/8 | 0 |
| suricata | Duration BN-HMM | 0.002499 | 0.2871 | 0/8 | 0 |
| suricata | Boosted-tree forecast | 0.001195 | 0.7210 | 3/8 | 4 |
| suricata | Learned conditional fusion | 0.001598 | 0.6601 | 5/8 | 2 |
| wazuh | Duration BN-HMM | 0.002574 | 0.1411 | 0/8 | 0 |
| wazuh | Boosted-tree forecast | 0.002402 | 0.6161 | 0/8 | 0 |
| wazuh | Learned conditional fusion | 0.002450 | 0.6660 | 0/8 | 0 |

With Suricata removed, fusion warns on 5/8 versus 3/8 campaigns for boosting and gives two versus four false episodes, but probability error and ranking are worse. With AMiner or Wazuh removed, neither issues a successful 15-minute warning. This is a specific coverage/false-alarm tradeoff, not robustness to all sensor failures. Complete stress results for every main method, both datasets and all horizons are in sensor_stress_summary.json and the per-campaign JSON files.

## Response-delay Decision Network sensitivity

The chance node is first-onset time; the decision node is Monitor/Restrict/Block/Isolate; an action-effect table and disruption/damage costs give expected loss. Compare delay-aware action selection with the same forecast ignoring delay. Both realized cost proxies respect actual assumed action delay. Evaluate all 27 combinations of damage 10/20/50, disruption scale .5/1/2 and assumed efficacy scale .5/.8/1.

| Dataset / forecast | Improved settings | Worse settings | Mean modeled cost reduction | Range across settings |
|---|---:|---:|---:|---:|
| ait / Tree: current counts only | 26/27 | 1/27 | 0.000672605 | [-0.00183061, 0.00570334] |
| ait / Tree: AMiner only | 21/27 | 6/27 | 0.000744897 | [-0.000391688, 0.00493776] |
| ait / Tree: Suricata only | 22/27 | 5/27 | 0.00197494 | [-0.00127457, 0.0109112] |
| ait / Tree: Wazuh only | 1/27 | 26/27 | -0.00257837 | [-0.0114437, 0.00124964] |
| ait / Learned conditional fusion | 11/27 | 16/27 | -0.0012532 | [-0.00977025, 0.00523048] |
| ait / Detector BN-HMM | 5/27 | 22/27 | -0.00330915 | [-0.0200548, 0.0117794] |
| ait / Duration BN-HMM | 12/27 | 15/27 | -0.00236051 | [-0.0238643, 0.00638136] |
| ait / Equal fusion | 18/27 | 9/27 | -0.00811648 | [-0.113515, 0.045314] |
| ait / Static BN | 15/27 | 11/27 | 0.000582618 | [-0.00131679, 0.0105506] |
| ait / Boosted-tree forecast | 12/27 | 15/27 | 0.000688511 | [-0.00143605, 0.00781719] |
| ait / Temporal logistic | 24/27 | 3/27 | 0.00384478 | [-0.00776148, 0.0223495] |
| darpa / Detector BN-HMM | 7/27 | 20/27 | -0.0407795 | [-0.218785, 0.147013] |
| darpa / Duration BN-HMM | 13/27 | 14/27 | 0.0042106 | [-0.224724, 0.161225] |
| darpa / Static BN | 11/27 | 16/27 | -0.0212294 | [-0.402597, 0.242466] |
| darpa / Boosted-tree forecast | 9/27 | 18/27 | -0.0922443 | [-1.31662, 0.467666] |
| darpa / Temporal logistic | 7/27 | 20/27 | -0.0770254 | [-0.483666, 0.356886] |

These are framewise assumed costs on passive logs. Actions were not executed; costs, delays and efficacy are not measured. Repeated per-minute actions are not a sequential response simulator. No measured prevention claim follows.

## Novelty and comparison with publications

HMM multistep prediction already appears in [Holgado et al., institutional record](https://portalcientifico.upm.es/en/ipublic/item/5643464) and [Dass et al., original paper](https://arxiv.org/abs/2106.02012). Explicit-duration HSMMs have prior cyber anomaly-detection work: [Tan and Xi, publisher abstract](https://www.sciencedirect.com/science/article/pii/S0096300308003342), DOI 10.1016/j.amc.2008.05.028. The indexed publisher abstract and introduction describe HSMM intrusion anomaly detection; full text was not accessible during the final check. [Cross-validated stacking](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html) is an established ensemble method. The combination is not a newly invented inference principle.

Our static BN, categorical HMM, expanded duration HMM, logistic and boosted-tree methods reproduce standard components with explicit settings; they do not reproduce complete named published systems. Their endpoints, observation mappings and metrics often differ. No published accuracy/F1 has been compared directly to our scores. Closest full-system reproductions and original held-out campaigns remain needed before claiming superiority to existing work. See ../../docs/NOVELTY_AUDIT.md.

## Defensible paper direction

**Working title:** Forecasting Cyberattack Onset from Multi-Sensor Alerts: Duration Models, Learned Fusion and Warning–Calibration Tradeoffs.

The candidate contribution is a reproducible empirical study of when learned fusion changes prospective warning behavior, with a separate packet-based DDoS transfer case study and explicit response assumptions. It includes substantive BN inference (Unit 1), an HMM with phase-duration expansion (Unit 2), and a Decision Network (Unit 3). The boosted tree is an additional forecast source and a mandatory strong baseline.

A supported preliminary claim: “On eight reused AIT scenarios, under a common validation warning rule, learned fusion maintained 5/8 30-minute episode warning coverage while reducing false-warning episodes from 20 to 5 relative to the boosted-tree forecaster, at the cost of worse Brier error and ranking. The reduction was concentrated in one scenario.”

Before a superiority or novelty paper submission: freeze this model and protocol; verify target execution times and telemetry availability from independent attacker/receipt logs; obtain fresh independent campaigns including benign-only and aborted attacks; reproduce the closest published prediction systems on this same endpoint; validate actual response delays/effects if response benefits are claimed. No further tuning on these eight traces can replace that fresh test. An empirical/benchmark paper may still be viable, depending on venue and stronger endpoint validation.

## Artifacts and verification

- summary.json, all_scores.csv: all six horizons, natural raw/calibrated scores and warning counts.
- fixed_thresholds.csv: .01/.05/.1/.5 operating points for every campaign and horizon.
- paired_comparisons.json: full signed campaign differences and descriptive intervals.
- decision_sensitivity.csv and decision_sensitivity_summary.json: all assumed cost/effect settings.
- predictions/: every fitted-fold validation/test probability array; *_metadata.json: vocabularies, bucket edges, durations and fusion coefficients.
- figures/: standalone PNG/PDF metric, all-campaign and DARPA forecast plots.
- reproducibility.json: source/config/cache/archive SHA-256 hashes and package versions.
- verification.json: thirteen regression tests, three research invariant suites and independent consistency checks for all 98 saved fold-prediction/report pairs.
- Application ingestion regressions cover label invariance and future-data independence. Research checks cover causal prefixes, replay invariance, probability coherence, duration transitions and delayed utility. Sensor stress refits reproduce saved natural supervised predictions to numerical tolerance.
- The research engine is separate from the legacy dashboard. Ingestion was corrected, but cached application tables, legacy XML local-time conversion and the dashboard’s hand-coded address boosts/event-count progression are not this validated forecasting method. Do not use dashboard accuracy as the research result.

Reproduce from project root with backend/research/run_extended_study.ps1. Data preparation reads archives in place; rerunning deterministically replaces only this study’s generated outputs. Earlier pilot reports remain intact.

# Evidence-association improvement pilot

Completed 4 October 2026.

This evaluates a bounded association-mixture prototype on eight AIT-ADS simulated scenarios. All models use the same 60-second grid and held-out scenario splits. The endpoint is scheduled privilege escalation, not DDoS launch or independently verified successful compromise.

## Verdict

**This first prototype does not establish a convincing forecasting improvement or academic novelty.** On natural traces, its calibrated Brier score is worse than exact deduplication at all three horizons. At 15 minutes, Brier is 0.002630 versus 0.002577 for exact deduplication (2.09% worse), 0.002728 for tuned deterministic grouping (3.58% better), and 0.002572 for direct logistic forecasting. The descriptive interval for its advantage over deterministic grouping includes zero. All five methods warn about zero of eight outcomes at this horizon under the specified validation-selected rule.

There are limited positive findings: natural-trace 15-minute average precision rises from 0.0703 with exact deduplication to 0.0726 with the prototype, and under the constructed alias/jitter stress it is 0.0797 versus 0.0345. These are ranking improvements in this pilot, not demonstrated improvements in reliable early warnings, real cross-sensor event association, or prevention. The stress mechanism resembles the constructed positives used to fit the matcher; transfer to other corruption mechanisms has not been tested. At 30 minutes on natural traces the calibrated prototype warns about one of eight outcomes and produces 26 false-warning episodes, compared with one outcome and 25 false episodes for exact deduplication.

Improvement can support an empirical paper contribution when the comparison is fair and reproducible. It does not establish that a method is original. The appropriate current claim is an exploratory evaluation with mixed results; a superiority or first-ever method claim is unsupported. This evaluates a limited prototype, so it also does not rule out a better event-association model.

## Complete outcome comparison

Brier is averaged across test scenarios; lower is better. AP is scenario-averaged average precision computed with sklearn.metrics.average_precision_score, not trapezoidal PR-curve area. The JSON field names pr_auc and mean_pr_auc are retained for compatibility and denote AP. Positive forecast timestamps are rare, so a low Brier alone is insufficient evidence of useful forecasting. Warnings use a validation-selected budget of at most one false-warning episode per 24 hours of negative forecast exposure and at most five negative warning minutes on the validation scenario. That budget is not guaranteed on test scenarios. Lead time includes only warned outcomes; misses are shown.

### natural

**scores**

| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min | Separate reports | 0.002775 | 0.0142 | 0/8 | — | 0 | 0 | 0.08659 |
| 5 min | Exact deduplication | 0.002773 | 0.0131 | 0/8 | — | 0 | 0 | 0.08667 |
| 5 min | Tuned deterministic grouping | 0.002778 | 0.0146 | 0/8 | — | 0 | 0 | 0.09026 |
| 5 min | Association-mixture prototype | 0.002774 | 0.0133 | 0/8 | — | 0 | 0 | 0.08662 |
| 5 min | Direct logistic forecaster | 0.000858 | 0.0022 | 0/8 | — | 0 | 0 | 0.01718 |
| 15 min | Separate reports | 0.012090 | 0.0801 | 0/8 | — | 0 | 0 | 0.34653 |
| 15 min | Exact deduplication | 0.012091 | 0.0763 | 0/8 | — | 0 | 0 | 0.34646 |
| 15 min | Tuned deterministic grouping | 0.012213 | 0.0715 | 0/8 | — | 0 | 0 | 0.35205 |
| 15 min | Association-mixture prototype | 0.012091 | 0.0769 | 0/8 | — | 0 | 0 | 0.34638 |
| 15 min | Direct logistic forecaster | 0.002571 | 0.0047 | 0/8 | — | 0 | 0 | 0.05155 |
| 30 min | Separate reports | 0.033067 | 0.1833 | 1/8 | 29.30 | 50 | 2153 | 0.36696 |
| 30 min | Exact deduplication | 0.033055 | 0.1853 | 1/8 | 29.30 | 50 | 2153 | 0.36709 |
| 30 min | Tuned deterministic grouping | 0.033454 | 0.1720 | 1/8 | 29.30 | 85 | 5115 | 0.37198 |
| 30 min | Association-mixture prototype | 0.033056 | 0.1869 | 1/8 | 29.30 | 49 | 2155 | 0.36696 |
| 30 min | Direct logistic forecaster | 0.005134 | 0.0089 | 0/8 | — | 0 | 0 | 0.10366 |

**calibrated_scores**

| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min | Separate reports | 0.000866 | 0.0124 | 0/8 | — | 0 | 0 | 0.01718 |
| 5 min | Exact deduplication | 0.000869 | 0.0127 | 0/8 | — | 0 | 0 | 0.01718 |
| 5 min | Tuned deterministic grouping | 0.000875 | 0.0124 | 0/8 | — | 0 | 0 | 0.01721 |
| 5 min | Association-mixture prototype | 0.000885 | 0.0128 | 0/8 | — | 0 | 0 | 0.01723 |
| 5 min | Direct logistic forecaster | 0.000859 | 0.0019 | 0/8 | — | 0 | 0 | 0.01718 |
| 15 min | Separate reports | 0.002577 | 0.0754 | 0/8 | — | 0 | 0 | 0.05155 |
| 15 min | Exact deduplication | 0.002577 | 0.0703 | 0/8 | — | 0 | 0 | 0.05155 |
| 15 min | Tuned deterministic grouping | 0.002728 | 0.0650 | 0/8 | — | 0 | 0 | 0.05180 |
| 15 min | Association-mixture prototype | 0.002630 | 0.0726 | 0/8 | — | 0 | 0 | 0.05162 |
| 15 min | Direct logistic forecaster | 0.002572 | 0.0041 | 0/8 | — | 0 | 0 | 0.05155 |
| 30 min | Separate reports | 0.017601 | 0.1323 | 1/8 | 29.30 | 56 | 2129 | 0.20989 |
| 30 min | Exact deduplication | 0.017386 | 0.1358 | 1/8 | 29.30 | 25 | 2250 | 0.20628 |
| 30 min | Tuned deterministic grouping | 0.020912 | 0.1301 | 1/8 | 29.30 | 60 | 5211 | 0.21012 |
| 30 min | Association-mixture prototype | 0.018997 | 0.1374 | 1/8 | 29.30 | 26 | 2251 | 0.20624 |
| 30 min | Direct logistic forecaster | 0.005135 | 0.0071 | 0/8 | — | 0 | 0 | 0.10357 |

### exact_replay

**scores**

| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min | Separate reports | 0.002797 | 0.0042 | 0/8 | — | 0 | 0 | 0.09325 |
| 5 min | Exact deduplication | 0.002773 | 0.0131 | 0/8 | — | 0 | 0 | 0.08667 |
| 5 min | Tuned deterministic grouping | 0.002778 | 0.0146 | 0/8 | — | 0 | 0 | 0.09026 |
| 5 min | Association-mixture prototype | 0.002774 | 0.0133 | 0/8 | — | 0 | 0 | 0.08662 |
| 5 min | Direct logistic forecaster | 0.000858 | 0.0022 | 0/8 | — | 0 | 0 | 0.01718 |
| 15 min | Separate reports | 0.012463 | 0.0281 | 0/8 | — | 0 | 0 | 0.35706 |
| 15 min | Exact deduplication | 0.012091 | 0.0763 | 0/8 | — | 0 | 0 | 0.34646 |
| 15 min | Tuned deterministic grouping | 0.012213 | 0.0715 | 0/8 | — | 0 | 0 | 0.35205 |
| 15 min | Association-mixture prototype | 0.012091 | 0.0769 | 0/8 | — | 0 | 0 | 0.34638 |
| 15 min | Direct logistic forecaster | 0.002571 | 0.0047 | 0/8 | — | 0 | 0 | 0.05155 |
| 30 min | Separate reports | 0.034120 | 0.1265 | 1/8 | 29.30 | 46 | 2043 | 0.37885 |
| 30 min | Exact deduplication | 0.033055 | 0.1853 | 1/8 | 29.30 | 50 | 2153 | 0.36709 |
| 30 min | Tuned deterministic grouping | 0.033454 | 0.1720 | 1/8 | 29.30 | 85 | 5115 | 0.37198 |
| 30 min | Association-mixture prototype | 0.033056 | 0.1869 | 1/8 | 29.30 | 49 | 2155 | 0.36696 |
| 30 min | Direct logistic forecaster | 0.005134 | 0.0089 | 0/8 | — | 0 | 0 | 0.10366 |

**calibrated_scores**

| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min | Separate reports | 0.000867 | 0.0033 | 0/8 | — | 0 | 0 | 0.01718 |
| 5 min | Exact deduplication | 0.000869 | 0.0127 | 0/8 | — | 0 | 0 | 0.01718 |
| 5 min | Tuned deterministic grouping | 0.000875 | 0.0124 | 0/8 | — | 0 | 0 | 0.01721 |
| 5 min | Association-mixture prototype | 0.000885 | 0.0128 | 0/8 | — | 0 | 0 | 0.01723 |
| 5 min | Direct logistic forecaster | 0.000859 | 0.0019 | 0/8 | — | 0 | 0 | 0.01718 |
| 15 min | Separate reports | 0.002578 | 0.0255 | 0/8 | — | 0 | 0 | 0.05155 |
| 15 min | Exact deduplication | 0.002577 | 0.0703 | 0/8 | — | 0 | 0 | 0.05155 |
| 15 min | Tuned deterministic grouping | 0.002728 | 0.0650 | 0/8 | — | 0 | 0 | 0.05180 |
| 15 min | Association-mixture prototype | 0.002630 | 0.0726 | 0/8 | — | 0 | 0 | 0.05162 |
| 15 min | Direct logistic forecaster | 0.002572 | 0.0041 | 0/8 | — | 0 | 0 | 0.05155 |
| 30 min | Separate reports | 0.017461 | 0.0893 | 1/8 | 29.30 | 52 | 2021 | 0.21403 |
| 30 min | Exact deduplication | 0.017386 | 0.1358 | 1/8 | 29.30 | 25 | 2250 | 0.20628 |
| 30 min | Tuned deterministic grouping | 0.020912 | 0.1301 | 1/8 | 29.30 | 60 | 5211 | 0.21012 |
| 30 min | Association-mixture prototype | 0.018997 | 0.1374 | 1/8 | 29.30 | 26 | 2251 | 0.20624 |
| 30 min | Direct logistic forecaster | 0.005135 | 0.0071 | 0/8 | — | 0 | 0 | 0.10357 |

### alias_jitter

**scores**

| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min | Separate reports | 0.002806 | 0.0061 | 0/8 | — | 0 | 0 | 0.09097 |
| 5 min | Exact deduplication | 0.002808 | 0.0047 | 0/8 | — | 0 | 0 | 0.09088 |
| 5 min | Tuned deterministic grouping | 0.002823 | 0.0041 | 0/8 | — | 0 | 0 | 0.09214 |
| 5 min | Association-mixture prototype | 0.002784 | 0.0146 | 0/8 | — | 0 | 0 | 0.08740 |
| 5 min | Direct logistic forecaster | 0.000858 | 0.0021 | 0/8 | — | 0 | 0 | 0.01718 |
| 15 min | Separate reports | 0.012317 | 0.0459 | 0/8 | — | 0 | 0 | 0.35464 |
| 15 min | Exact deduplication | 0.012325 | 0.0375 | 0/8 | — | 0 | 0 | 0.35544 |
| 15 min | Tuned deterministic grouping | 0.012432 | 0.0170 | 0/8 | — | 0 | 0 | 0.35736 |
| 15 min | Association-mixture prototype | 0.012145 | 0.0826 | 0/8 | — | 0 | 0 | 0.34781 |
| 15 min | Direct logistic forecaster | 0.002571 | 0.0049 | 0/8 | — | 0 | 0 | 0.05155 |
| 30 min | Separate reports | 0.033597 | 0.1585 | 1/8 | 29.30 | 49 | 2052 | 0.37594 |
| 30 min | Exact deduplication | 0.033659 | 0.1316 | 1/8 | 29.30 | 49 | 2052 | 0.37706 |
| 30 min | Tuned deterministic grouping | 0.034001 | 0.0992 | 1/8 | 29.30 | 80 | 4969 | 0.38181 |
| 30 min | Association-mixture prototype | 0.033255 | 0.1729 | 1/8 | 29.30 | 50 | 2134 | 0.36871 |
| 30 min | Direct logistic forecaster | 0.005135 | 0.0087 | 0/8 | — | 0 | 0 | 0.10368 |

**calibrated_scores**

| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min | Separate reports | 0.000867 | 0.0050 | 0/8 | — | 0 | 0 | 0.01718 |
| 5 min | Exact deduplication | 0.000869 | 0.0048 | 0/8 | — | 0 | 0 | 0.01718 |
| 5 min | Tuned deterministic grouping | 0.000876 | 0.0024 | 0/8 | — | 0 | 0 | 0.01721 |
| 5 min | Association-mixture prototype | 0.000885 | 0.0144 | 0/8 | — | 0 | 0 | 0.01723 |
| 5 min | Direct logistic forecaster | 0.000859 | 0.0017 | 0/8 | — | 0 | 0 | 0.01718 |
| 15 min | Separate reports | 0.002578 | 0.0428 | 0/8 | — | 0 | 0 | 0.05155 |
| 15 min | Exact deduplication | 0.002578 | 0.0345 | 0/8 | — | 0 | 0 | 0.05155 |
| 15 min | Tuned deterministic grouping | 0.002730 | 0.0100 | 0/8 | — | 0 | 0 | 0.05182 |
| 15 min | Association-mixture prototype | 0.002631 | 0.0797 | 0/8 | — | 0 | 0 | 0.05162 |
| 15 min | Direct logistic forecaster | 0.002572 | 0.0039 | 0/8 | — | 0 | 0 | 0.05155 |
| 30 min | Separate reports | 0.017566 | 0.1152 | 1/8 | 29.30 | 53 | 2036 | 0.21413 |
| 30 min | Exact deduplication | 0.017360 | 0.0946 | 1/8 | 29.30 | 21 | 2145 | 0.21110 |
| 30 min | Tuned deterministic grouping | 0.020942 | 0.0668 | 1/8 | 29.30 | 59 | 5060 | 0.21264 |
| 30 min | Association-mixture prototype | 0.019015 | 0.1258 | 1/8 | 29.30 | 25 | 2230 | 0.20722 |
| 30 min | Direct logistic forecaster | 0.005136 | 0.0067 | 0/8 | — | 0 | 0 | 0.10357 |

## Paired differences on natural traces

Negative Brier differences favor the prototype. Bootstrap intervals below are descriptive scenario-resampling intervals, not confirmatory significance tests: training folds overlap and the eight scenarios share related attack templates. No multiple-comparison-adjusted success claim is made.

| Scoring | Horizon | Baseline | Mean Brier difference | Descriptive interval | Better / worse / tied folds |
|---|---|---|---:|---|---|
| scores | 5 min | Exact deduplication | 0.0000003 | [-0.0000001, 0.0000008] | 1 / 7 / 0 |
| scores | 5 min | Tuned deterministic grouping | -0.0000041 | [-0.0000387, 0.0000209] | 3 / 5 / 0 |
| scores | 5 min | Direct logistic forecaster | 0.0019154 | [0.0004694, 0.0035125] | 1 / 7 / 0 |
| scores | 15 min | Exact deduplication | 0.0000008 | [-0.0000015, 0.0000029] | 2 / 6 / 0 |
| scores | 15 min | Tuned deterministic grouping | -0.0001216 | [-0.0003946, 0.0000274] | 3 / 5 / 0 |
| scores | 15 min | Direct logistic forecaster | 0.0095205 | [0.0015208, 0.0218420] | 1 / 7 / 0 |
| scores | 30 min | Exact deduplication | 0.0000014 | [-0.0000067, 0.0000097] | 3 / 5 / 0 |
| scores | 30 min | Tuned deterministic grouping | -0.0003973 | [-0.0012079, 0.0000698] | 3 / 5 / 0 |
| scores | 30 min | Direct logistic forecaster | 0.0279225 | [0.0035660, 0.0639615] | 3 / 5 / 0 |
| calibrated_scores | 5 min | Exact deduplication | 0.0000160 | [-0.0000026, 0.0000503] | 3 / 3 / 2 |
| calibrated_scores | 5 min | Tuned deterministic grouping | 0.0000095 | [0.0000000, 0.0000250] | 2 / 4 / 2 |
| calibrated_scores | 5 min | Direct logistic forecaster | 0.0000261 | [-0.0000004, 0.0000756] | 4 / 3 / 1 |
| calibrated_scores | 15 min | Exact deduplication | 0.0000538 | [-0.0000027, 0.0001643] | 5 / 1 / 2 |
| calibrated_scores | 15 min | Tuned deterministic grouping | -0.0000977 | [-0.0002928, 0.0000008] | 5 / 1 / 2 |
| calibrated_scores | 15 min | Direct logistic forecaster | 0.0000584 | [-0.0000055, 0.0001820] | 4 / 3 / 1 |
| calibrated_scores | 30 min | Exact deduplication | 0.0016109 | [-0.0000339, 0.0048684] | 5 / 2 / 1 |
| calibrated_scores | 30 min | Tuned deterministic grouping | -0.0019152 | [-0.0062687, 0.0005496] | 5 / 2 / 1 |
| calibrated_scores | 30 min | Direct logistic forecaster | 0.0138612 | [-0.0000633, 0.0389066] | 5 / 3 / 0 |

## Checks and limitations

- All eight splits have disjoint fitting, calibration, and test scenario identities. Nine numerical/causal pilot invariants passed before scoring.
- Exact replays produce precisely zero forecast change for exact deduplication, deterministic grouping, the association prototype, and the direct forecaster. This is a correctness property, not a unique advantage of the proposed method.
- Alias/jitter stress adds copies to 10% of existing records, with changed report IDs and 0.05–2 second timestamp delays. Natural results remain the main comparison; only one fixed stress seed per held-out scenario was used.
- The matcher uses constructed replay positives and different original records as proxy negatives. Different stored reports may refer to the same real event. Real event-identity truth and genuine cross-sensor corroboration have not been validated.
- The prototype marginalizes disjoint report pairs into count-bucket likelihoods. It assumes state-independent association weights and conditional independence of count categories. It does not implement a globally coherent model of all latent event identities and sensor error dependencies.
- Count bins and broad observable message categories are a limited representation; this study does not rule out other observation models. Models are fitted separately to their corresponding evidence representation, and deterministic grouping tolerance is selected on validation data.
- Alert timestamps are treated as availability timestamps for retrospective replay. Actual live collection delays and telemetry health are not measured. Start exposure is the UTC day containing the first retained alert; initial unobserved minutes may be counted as empty observations.
- Scheduled attack-stage labels are the target. Exfiltration was excluded because onset ordering was inconsistent in six published scenario label sequences; raw victim/attacker logs still need independent validation for a submission.
- Each run contributes one attack outcome; the long background traces do not create thousands of independent positive episodes. Training and calibration use six and one scenarios respectively, so calibration and warning thresholds may vary substantially.
- The modeled response cost uses the same binary Monitor/Block expected-cost decision for every method: false action cost 1, missed imminent outcome cost 20, assumed perfect immediate action effect. The threshold is 1/21. It is a hypothetical, framewise decision analysis, not measured prevention or the dashboard's full response policy.
- Separate calibration models are fitted on the validation scenario for each horizon, with monotonic horizon correction. This is exploratory calibration with very few positive outcomes.
- The warning rule considers a fixed grid of thresholds and may select no warnings. These results describe that rule, not the best achievable warning policy at every operating point.

## Reproduce

```powershell
python backend/research/fetch_ait.py
python backend/research/evidence_pilot.py prepare
python backend/research/evidence_pilot.py checks
python backend/research/evidence_pilot.py run
python backend/research/report_evidence_pilot.py
```

Inputs: [AIT-ADS](https://zenodo.org/records/8263181); download checksums are verified against the publisher record. Original dashboard experiments and SQLite tables were not used for these outcome scores. All fold-level scores, transformations, code, and runtime versions are preserved alongside this report.

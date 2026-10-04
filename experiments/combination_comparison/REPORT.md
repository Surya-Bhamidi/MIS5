# Are our combinations better than other work?

Assessment: 4 October 2026.

**No demonstrated superiority over published cyberattack-forecasting systems.** Component tests show a useful ranking contribution from temporal filtering, but the present BN-HMM is mathematically the same forecaster as a conventional HMM with factorized categorical emissions. The uncertain-association addition has mixed results. Published results inspected below do not match our dataset, endpoint, horizons, and evaluation protocol, and none of those complete named systems was reproduced in this extension.

## Same-data component and standard-method experiments

Eight AIT-ADS scenarios; six fitting, one calibration, one test scenario per rotating fold. All predictions use past-only observations on a 60-second clock. The endpoint is scheduled privilege escalation. New alternatives use ordinary exact deduplication. Temporal supervised baselines use current count buckets and trailing 5- and 15-minute means. Settings were written in [the extension protocol](../combination_comparison_protocol.md) before their outcome scoring. The original five comparisons are reused after verifying exact BN-HMM reproduction.

At 15 minutes, temporal filtering reduces calibrated Brier by 0.42% versus the no-filter ablation and raises scenario-averaged average precision from 0.0040 to 0.0703. However, every tested method warns about zero of eight outcomes at that horizon under the specified threshold-selection rule. Better ranking therefore has not produced useful warnings at that operating point. Direct logistic forecasting has slightly lower 15-minute Brier than BN-HMM but much lower average precision; no method wins every metric. The positive timestamps are rare, so Brier alone is insufficient.

The no-filter ablation uses a training-derived fixed state-occupancy prior and the same learned Markov onset projection. It removes sequential filtering, but is not a pure static BN forecasting algorithm. The independent conventional HMM implementation matches BN-HMM raw predictions on all held-out bins with maximum absolute difference 2.07e-14. Separate calibration fits can amplify floating-point differences slightly; their aggregate scores are effectively equal. Thus there is no measured improvement attributable merely to calling its observation model a BN.

The same hypothetical binary decision rule is applied to every forecast. It assumes a false action cost of 1, missed imminent outcome cost of 20, and perfect immediate action effect. This does not test the complete Decision Network policy or measured prevention. A downstream response policy does not change forecast accuracy unless it changes subsequent observations/outcomes.

### scores

Brier lower is better; AP higher is better. Each score is scenario-averaged.

| Horizon | Method | Brier | AP | Warned / 8 | False episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|
| 5 min | BN-HMM, separate reports | 0.002775 | 0.0142 | 0/8 | 0 | 0 | 0.08659 |
| 5 min | BN-HMM, exact deduplication | 0.002773 | 0.0131 | 0/8 | 0 | 0 | 0.08667 |
| 5 min | BN-HMM, deterministic grouping | 0.002778 | 0.0146 | 0/8 | 0 | 0 | 0.09026 |
| 5 min | BN-HMM, uncertain association prototype | 0.002774 | 0.0133 | 0/8 | 0 | 0 | 0.08662 |
| 5 min | Direct logistic, current counts | 0.000858 | 0.0022 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | BN observation + onset projection, no filter | 0.000952 | 0.0019 | 0/8 | 0 | 0 | 0.01792 |
| 5 min | Conventional factorized categorical HMM | 0.002773 | 0.0131 | 0/8 | 0 | 0 | 0.08667 |
| 5 min | Logistic, causal temporal counts | 0.000859 | 0.0019 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | Gradient boosting, causal temporal counts | 0.001023 | 0.0113 | 0/8 | 0 | 0 | 0.01995 |
| 15 min | BN-HMM, separate reports | 0.012090 | 0.0801 | 0/8 | 0 | 0 | 0.34653 |
| 15 min | BN-HMM, exact deduplication | 0.012091 | 0.0763 | 0/8 | 0 | 0 | 0.34646 |
| 15 min | BN-HMM, deterministic grouping | 0.012213 | 0.0715 | 0/8 | 0 | 0 | 0.35205 |
| 15 min | BN-HMM, uncertain association prototype | 0.012091 | 0.0769 | 0/8 | 0 | 0 | 0.34638 |
| 15 min | Direct logistic, current counts | 0.002571 | 0.0047 | 0/8 | 0 | 0 | 0.05155 |
| 15 min | BN observation + onset projection, no filter | 0.002678 | 0.0052 | 0/8 | 0 | 0 | 0.05296 |
| 15 min | Conventional factorized categorical HMM | 0.012091 | 0.0763 | 0/8 | 0 | 0 | 0.34646 |
| 15 min | Logistic, causal temporal counts | 0.002576 | 0.0036 | 0/8 | 0 | 0 | 0.05168 |
| 15 min | Gradient boosting, causal temporal counts | 0.003057 | 0.0099 | 0/8 | 0 | 0 | 0.05850 |
| 30 min | BN-HMM, separate reports | 0.033067 | 0.1833 | 1/8 | 50 | 2153 | 0.36696 |
| 30 min | BN-HMM, exact deduplication | 0.033055 | 0.1853 | 1/8 | 50 | 2153 | 0.36709 |
| 30 min | BN-HMM, deterministic grouping | 0.033454 | 0.1720 | 1/8 | 85 | 5115 | 0.37198 |
| 30 min | BN-HMM, uncertain association prototype | 0.033056 | 0.1869 | 1/8 | 49 | 2155 | 0.36696 |
| 30 min | Direct logistic, current counts | 0.005134 | 0.0089 | 0/8 | 0 | 0 | 0.10366 |
| 30 min | BN observation + onset projection, no filter | 0.005287 | 0.0120 | 0/8 | 0 | 0 | 0.10673 |
| 30 min | Conventional factorized categorical HMM | 0.033055 | 0.1853 | 1/8 | 50 | 2153 | 0.36709 |
| 30 min | Logistic, causal temporal counts | 0.005109 | 0.0992 | 2/8 | 7 | 37 | 0.09540 |
| 30 min | Gradient boosting, causal temporal counts | 0.005567 | 0.0614 | 0/8 | 5 | 7 | 0.10188 |

### calibrated_scores

Brier lower is better; AP higher is better. Each score is scenario-averaged.

| Horizon | Method | Brier | AP | Warned / 8 | False episodes | Negative warning minutes | Modeled cost |
|---|---|---:|---:|---:|---:|---:|---:|
| 5 min | BN-HMM, separate reports | 0.000866 | 0.0124 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | BN-HMM, exact deduplication | 0.000869 | 0.0127 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | BN-HMM, deterministic grouping | 0.000875 | 0.0124 | 0/8 | 0 | 0 | 0.01721 |
| 5 min | BN-HMM, uncertain association prototype | 0.000885 | 0.0128 | 0/8 | 0 | 0 | 0.01723 |
| 5 min | Direct logistic, current counts | 0.000859 | 0.0019 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | BN observation + onset projection, no filter | 0.000872 | 0.0016 | 0/8 | 0 | 0 | 0.01736 |
| 5 min | Conventional factorized categorical HMM | 0.000869 | 0.0127 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | Logistic, causal temporal counts | 0.000859 | 0.0016 | 0/8 | 0 | 0 | 0.01718 |
| 5 min | Gradient boosting, causal temporal counts | 0.000892 | 0.0017 | 0/8 | 0 | 0 | 0.01904 |
| 15 min | BN-HMM, separate reports | 0.002577 | 0.0754 | 0/8 | 0 | 0 | 0.05155 |
| 15 min | BN-HMM, exact deduplication | 0.002577 | 0.0703 | 0/8 | 0 | 0 | 0.05155 |
| 15 min | BN-HMM, deterministic grouping | 0.002728 | 0.0650 | 0/8 | 0 | 0 | 0.05180 |
| 15 min | BN-HMM, uncertain association prototype | 0.002630 | 0.0726 | 0/8 | 0 | 0 | 0.05162 |
| 15 min | Direct logistic, current counts | 0.002572 | 0.0041 | 0/8 | 0 | 0 | 0.05155 |
| 15 min | BN observation + onset projection, no filter | 0.002587 | 0.0040 | 0/8 | 0 | 0 | 0.05182 |
| 15 min | Conventional factorized categorical HMM | 0.002577 | 0.0703 | 0/8 | 0 | 0 | 0.05155 |
| 15 min | Logistic, causal temporal counts | 0.002575 | 0.0034 | 0/8 | 0 | 0 | 0.05162 |
| 15 min | Gradient boosting, causal temporal counts | 0.002620 | 0.0041 | 0/8 | 0 | 0 | 0.05331 |
| 30 min | BN-HMM, separate reports | 0.017601 | 0.1323 | 1/8 | 56 | 2129 | 0.20989 |
| 30 min | BN-HMM, exact deduplication | 0.017386 | 0.1358 | 1/8 | 25 | 2250 | 0.20628 |
| 30 min | BN-HMM, deterministic grouping | 0.020912 | 0.1301 | 1/8 | 60 | 5211 | 0.21012 |
| 30 min | BN-HMM, uncertain association prototype | 0.018997 | 0.1374 | 1/8 | 26 | 2251 | 0.20624 |
| 30 min | Direct logistic, current counts | 0.005135 | 0.0071 | 0/8 | 0 | 0 | 0.10357 |
| 30 min | BN observation + onset projection, no filter | 0.005151 | 0.0115 | 0/8 | 0 | 0 | 0.10395 |
| 30 min | Conventional factorized categorical HMM | 0.017386 | 0.1358 | 1/8 | 25 | 2250 | 0.20628 |
| 30 min | Logistic, causal temporal counts | 0.005045 | 0.0986 | 1/8 | 1 | 4 | 0.09364 |
| 30 min | Gradient boosting, causal temporal counts | 0.005202 | 0.0382 | 0/8 | 5 | 7 | 0.10552 |

## Published work checked and why its scores cannot be ranked against ours

| Work | What is established by the inspected primary source | Comparison status |
|---|---|---|
| [Devarakonda et al., 2012: BN + HMM](https://www.sciencedirect.com/science/article/pii/S221201731200360X) | Publisher abstract describes KDDCUP normal/attack connection classification and a BN structure used for HMM transitions. | Detection target differs from scheduled-onset forecasting; not reproduced. |
| [Sendi et al., 2012: optimized alerts + HMM](https://citeseerx.ist.psu.edu/document?doi=3aa6e5a9a9bfb27bf32fbab8b2c194ab42bad1dc&repid=rep1&type=pdf) | Indexed original abstract reports multistep prediction on Lincoln Laboratory 2000 data. | Closely related objective, different benchmark/protocol; full text unavailable in this check. |
| [Li et al., 2020: hidden Markov + probabilistic inference](https://www.sciencedirect.com/science/article/abs/pii/S0167404820302479) | Indexed publisher preview describes attack-plan reasoning. | Relevant integration precedent; complete methods/results not reverified or reproduced here. |
| [Ingale et al., 2020: HMM + Naive Bayes](https://ieeexplore.ieee.org/document/9155895) | Primary IEEE record verifies the titled combination. | Full method, dataset, and numerical results unavailable; cannot infer them from citations to the work. |
| [Zhang et al., 2022: pre-trained HMM](https://www.mdpi.com/1424-8220/22/8/2874) | Author article describes attack-stage detection on DARPA, DEFCON21, and ISCXIDS2012; experiment alerts contain no benign examples. | Stage-decoding accuracy differs from pre-onset warnings with negative exposure. |
| [PARD-SSM, April 2026 preprint](https://arxiv.org/html/2604.02299v1) | Reports F1 0.982 on CICIDS2017, 0.971 on UNSW-NB15, and about eight minutes of early warning; Section 9.5 describes smoothed posteriors. | Different outcomes/splits; causal filtering versus smoothing must be clarified before a fair online comparison. Claims not independently reproduced. |
| [AlertBERT, February 2026 preprint](https://arxiv.org/html/2602.06534v1) | Groups alerts on AIT-derived augmented data and evaluates pairwise clustering ROC/AUC. [Author code](https://github.com/ait-aecid/AlertBERT) is available. | Same source dataset family, different grouping target/metric; no forecast comparison completed. |

AlertBERT is a concrete external grouping comparator for a later experiment: apply a causal version of its grouping to the same forecaster and score the same future-onset targets. Its reported embedding readout pads each sequence on both ends, so simply replaying the published forensic evaluation as an online predictor could use later alerts. Verify availability of every input, fit embeddings/grouping parameters on fitting runs only, and label any adaptation rather than claiming exact reproduction.

## Limits and claim supported

This is an exploratory eight-scenario pilot with related attack templates, very few outcomes, one calibration run per fold, and a coarse warning threshold grid. Baseline settings were fixed rather than exhaustively tuned. The association matcher lacks real event-identity validation. Stage timestamps remain scheduled labels, not independently verified successful compromises. Retrospective alert timestamps are assumed to represent availability. All limitations in the [first pilot report](../evidence_pilot/REPORT.md) still apply. Campaign-resampling intervals in paired_comparisons.json are descriptive; overlapping training folds and related scenarios preclude treating them as confirmatory significance tests.

The defensible conclusion is that temporal filtering improves ranking over the no-filter ablation in this pilot, while the chosen BN-HMM observation model is equivalent to a standard HMM. Overall forecasting superiority, an advantage from the complete three-unit combination, and superiority over named published methods remain unestablished.

## Reproduce

```powershell
python backend/research/compare_combinations.py
python backend/research/report_combination_comparison.py
```

Requires the prepared AIT-ADS inputs and completed original pilot. All 72 natural-trace scenario/method evaluations, 432 score rows, equivalence checks, and paired comparisons are preserved in this directory. Source hashes are in source_sha256.json; runtime versions are recorded in ../evidence_pilot/reproducibility.json.

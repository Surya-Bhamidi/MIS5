# Current research version

The current preset is **pooled-calibrated fixed .25 state fusion**, with
**30-minute early warning** as its primary use case. Further model development
is deferred. This is a development choice after reviewing test results; it
does not replace the failed prespecified adaptive-selector result in the paper.
There is no single model that is best across all measured criteria.

The complete forecast uses 75% counts-only boosted-tree risk and 25% risk from
counts plus inferred BN/HMM stage features, followed by campaign-pooled sigmoid
calibration. Use the same fixed blend at all six horizons, preserving the
coherent onset distribution required for response-delay decisions. Do not
splice in the original 15-minute probabilities without separately evaluating
that new combination.

* Unit 1: BN observation likelihood, including omission of unavailable sensors.
* Unit 2: causal forward HMM state estimates and their trailing summaries.
* Unit 3: Decision Network using onset probabilities, delay and assumed costs.

The inference entry point is `predict_current` in
`backend/research/selective_fusion.py`. It requires a fitted expert matching
declared availability and that fold's pooled calibrators. No sensor input
returns insufficient evidence and no recommended action. The recommendation
does not execute a defense. The legacy demonstration application remains a
separate phase-classification interface, not evidence for these forecasts.

Frozen fold predictions, calibration/threshold metadata and a hash manifest
are under `experiments/current_version`. Run
`python backend/research/freeze_current_version.py` to rebuild that package from
the already verified selective-fusion artifacts. This performs no training,
tuning or data download. Eight fold-specific forecasts are retained; no new
all-eight-campaign deployment model or independent campaign is claimed.

Run `python backend/research/verify_current_version.py` to check the regression
suite, exact archive copies, frozen thresholds and one refitted campaign's
agreement with the saved forecast. It also checks causal prefixes and
no-sensor abstention. Rebuild the package afterward to refresh its hashes.

## Tested evidence

At the same strict validation alarm budget of one false episode per 24 negative
hours and at most five negative warning minutes:

| 30-minute successful-root forecast | Original calibrated counts | Current preset |
|---|---:|---:|
| Timely new warnings | 4/8 | 5/8 |
| Mean Brier | .0015254 | .0014606 |
| Mean AP | .8320 | .8275 |
| False episodes | 19 | 5 |

This is a conditional gain: the aggregate false-episode reduction is dominated
by wheeler and reverses when it is excluded. Matched pooled counts has three
timely warnings and one false episode; the blend adds warnings with additional
alarm burden. The 15-minute current preset gives 4/8 warnings, four false
episodes and worse Brier than the original 15-minute counts baseline, which
remains the reference for that horizon. External CAM warnings remain 0/3 at
15/30 minutes. Response effects are assumed rather than physically tested.

All experimental alternatives, negative results and original baselines remain
in [the selective-fusion report](../experiments/selective_fusion/REPORT.md).
This preset is useful for the specified exploratory 30-minute task; broad
superiority, architectural novelty and publication acceptance are unestablished.

# Exploratory forecast feature ablations

Declared after the extended/fusion results, 4 October 2026. These comparisons
isolate representation choices; they do not introduce or tune a new candidate.
The eight AIT scenarios remain reused development evidence.

Use exactly the existing boosted-tree settings, six horizons, outer splits,
calibration and warning selector. Compare current counts alone with current
counts plus trailing 5/15/60-minute means. Separately fit one forecaster for
each individual sensor using the temporal features. Unlike outage stress,
these single-sensor baselines are trained on that reduced input. Retain all
four ablation outcomes and compare with the full three-sensor temporal tree.
Do not choose model settings or fusion weights from these results.

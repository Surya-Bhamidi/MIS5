# Combination comparison extension

Written before extension outcome scoring, 4 October 2026. Exploratory extension
of the existing AIT-ADS pilot; no confirmatory success criterion is declared.

Keep the original 60-second observations, scheduled privilege-escalation
endpoint, eight rotating 6/1/1 fitting/calibration/test splits, horizons,
calibration routine, warning threshold selection, and hypothetical response
costs. Use ordinary exact deduplication for the new alternatives.

1. BN observation inference without temporal filtering: estimate a fixed
   state-occupancy prior on fitting runs, infer state from the current counts,
   and use the same learned Markov first-onset projection. This removes the
   sequential filtering component; it is not a pure static BN forecaster.
2. Conventional HMM with factorized categorical emissions: independently
   calculate the ordinary HMM forward recursion and first-onset risk. Under
   this observation model it should equal the BN-HMM implementation. Test
   equality on every held-out clock bin, not just aggregate metrics.
3. Logistic future-outcome forecasting with causal temporal count summaries:
   current bucket indices plus trailing 5- and 15-minute means, including the
   current observation. C=1, max_iter=1000, no class balancing.
4. Histogram gradient boosting using those same temporal features:
   max_iter=100, learning_rate=.08, max_leaf_nodes=15, min_samples_leaf=20,
   l2_regularization=1, early_stopping=False, random_state=1729.

No new model or feature selection uses held-out results. Report calibrated and
uncalibrated metrics at every horizon, warning coverage and false warnings.
Combine with previous natural-trace scores after verifying exact BN-HMM
reproduction. These are local component/standard-method comparisons, not
faithful reproductions of named published cyberattack systems. Any published
score comparison must document dataset, target, horizon, inputs, split,
warning policy, and metric differences; incompatible scores are not ranked.

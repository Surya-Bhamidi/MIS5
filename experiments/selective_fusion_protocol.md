# Selective fusion with campaign-based fitting predictions

This development round follows the failed state-feature and confirmation
experiments. All eight AIT campaigns and the three CAM proxies were previously
inspected. This protocol precedes the new results; it is exploratory, not
untouched confirmation. Preserve every earlier experiment and all new losses.

Primary question: can horizon- and availability-specific blending improve
probability quality and timely new warnings relative to the matching counts
expert? The stated operational target is more than four of eight timely
15-minute root warnings with no more than three false episodes; this is a
comparison target, not a promised result or a test-set selection criterion.

* Keep the eight outer splits: six fitting campaigns, next campaign for alarm
  thresholds, one test campaign. No outer validation/test labels fit fusion
  weights or calibrators.
* Within the six fitting campaigns, hold each campaign out in turn. Fit the
  counts and BN/HMM-state augmented trees to the other five. Their vocabulary,
  count bins, BN tables and state parameters exclude the held campaign.
  Augmented training features themselves use leave-one-campaign-out state
  inference fitted on the other four of those five campaigns. Shared fitting
  vocabulary within that inner five is allowed; stage/count fitting excludes
  the inner state-feature campaign. Every held forecast is forward/past-only.
* Use unchanged boosting hyperparameters, the existing BN likelihood with
  fixed tempering and geometric HMM filter, and all seven sensor subsets.
  Cache unique five-campaign fits with source/data hashes and audit every
  nested split, actual state-feature use and a fitted prediction prefix.
* Per sensor subset and horizon choose a raw convex blend weight from
  {0,.1,.25,.5,1}. Minimize the mean of the six held-campaign Brier errors,
  normalized by the counts-only mean error, plus .01 times the weight. Ties
  favor weight zero. Selection uses raw fitting-campaign forecasts, not
  scores from the final calibrator or the outer test. Horizon order is repaired
  by a cumulative maximum only along the horizon axis.
* After selecting weights, fit six nonnegative-slope sigmoid calibrators to
  pooled held-campaign forecasts from the six fitting campaigns. Campaigns
  have equal total sample weight; the overall sample weight equals the total
  pre-outcome bin count. Reject a negative slope in favor of the weighted
  target prior. Fixed LogisticRegression C=1, max_iter=1000. Apply the fitted
  transforms to original six-campaign expert forecasts and repair horizon
  order. Fit-size differences (five for fitting forecasts versus six for
  application) and reuse of fitting forecasts for selection/calibration are
  limitations, not a claim of unbiased inner performance.
* Retain six fixed variants: raw counts, raw selective blend, pooled-calibrated
  counts, pooled-calibrated state augmentation, pooled-calibrated fixed .25
  blend, and pooled-calibrated selective blend. The matching pooled counts
  variant isolates fusion from the calibration change. Original single-
  campaign calibrated counts and fusion remain additional frozen references.
* Unit 1 BN observation inference and Unit 2 forward HMM states feed the state
  branch. Report every weight and actual output change versus counts; a zero
  weight does not demonstrate state-model benefit. Unit 3 retains the same
  delay-aware Decision Network and 27 damage/effect/disruption settings.
  Static declared availability and no-sensor abstention remain unchanged.
* Select strict alarm thresholds on the separate outer validation campaign,
  at budgets 0/.25/1/4 false episodes per 24 negative hours and at most five
  negative warning minutes. Retain the same threshold algorithm and six
  horizons. Score scheduled and successful-root endpoints; shift natural
  forecasts by 0/1/2/5 minutes. These are latency sensitivity replays, not
  measured alert receipt times. Test thresholds are frozen.
* Reuse the fox split for the known three CAM executed-tactic proxies with
  Wazuh/Suricata present and AMiner absent; do not tune on CAM. Report missing
  exposure as undefined rates. No additional independent campaign is created.
* Report original and matched-calibration baselines, all probability/ranking/
  warning metrics, campaign dependence including removal of wheeler, sensor
  losses, raw/calibration ablations, assumed utility and the external result.
  Do not pick the winning variant from test results or claim physical defense,
  architectural priority or complete published-system superiority.

Outputs: `experiments/selective_fusion`. Verify nested exclusion, raw reference
equality, fitting-only selector/calibration, saved probabilities, frozen alarm
constraints, independent metrics, state contribution and decision arithmetic.

Source references: [calibration](https://scikit-learn.org/stable/modules/calibration.html),
[campaign/group cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html).

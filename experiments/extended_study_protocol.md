# Extended exploratory forecasting and response study

Declared before new model outcome scoring, 4 October 2026. The earlier AIT
test results informed this extension, so AIT is reused development evidence,
not an untouched confirmatory test. Preserve all earlier negative results.

- Use exact-deduplicated detector identifiers from AIT, selected from fitting
  runs only. AMiner training-mode records are excluded using their observed
  flags. Keep the scheduled privilege-escalation target and original clock.
- Recover both full packet captures in each local DARPA tar.gz, including
  background traffic. Classifier features are anonymous traffic counts,
  protocol/port indicators and source/target cardinalities. Phase filenames,
  attacker/victim identities and XML attack-session membership are never input.
  Ground truth comes from separate XML phase annotations plus verification of
  the documented victim's actual ACK flood. Use EST in March and EDT in April,
  validated against capture timestamps. The target is flood emission, not
  successful denial of service. These remain just two related campaigns.
- AIT uses the previous rotating 6 fitting / 1 validation / 1 test split.
  DARPA uses two leave-one-campaign-out transfers with fixed method settings,
  training-only threshold selection, and no independent calibration run.
  DARPA results are small case studies, never generalization proof.
- Forecast within 1, 2, 5, 10, 15 and 30 minutes; compare every horizon.
  Main report emphasizes 5/15/30-minute pre-onset outcomes. Use common causal
  observations, timestamps, endpoint labels and exposure for all methods.
- Compare the original broad-category BN-HMM where available, ordinary
  detector-count HMM, explicit-duration age-expanded HMM, static BN with the
  same onset projection, and direct logistic/gradient-boosted forecasts.
  Supervised baselines receive current log-counts plus trailing 5/15/60-minute
  means. Detector vocabulary and all parameters use fitting scenarios only.
- The explicit-duration model is established semi-Markov modeling, implemented
  as an expanded HMM. Learn phase durations on fitting runs with a lognormal
  hazard, minimum log-scale standard deviation .5. Benign waiting remains
  geometric. This tests a duration-aware combination, not a first-ever HSMM.
- All methods use the same warning selector over validation probability
  quantiles plus positive-period scores. Budget: at most one false warning per
  24 negative hours, no more than five negative warning minutes. Also report
  fixed probability thresholds .01/.05/.1/.5 to reveal threshold dependence.
  Do not claim an advantage from fixing the original coarse threshold grid.
- Evaluate a Decision Network with onset-time chance bins and action-effect
  tables: Monitor (delay 0, effect 0, disruption 0), Restrict (delay 2 min,
  effect .45, disruption .1), Block (delay 5, effect .8, disruption .5), Isolate
  (delay 1, effect .95, disruption 2); outcome damage 20. Compare the identical
  forecast with a policy ignoring delays. This is assumed, framewise utility,
  not actual prevention. Report sensitivity to costs/effects, not just one win.
- Stress sensor removals equally across methods, exact replay invariance,
  probability coherence, causal prefixes and calibration. Do not count altered
  versions of a campaign as independent data. Preserve configuration hashes,
  fold predictions, all scores and campaign-level paired differences.
- Named published systems require faithful reproduction or explicit adaptation.
  No cross-dataset accuracy percentage will be used as proof of superiority.

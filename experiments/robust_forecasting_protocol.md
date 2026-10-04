# Revised forecasting experiment protocol

Specified before scoring the new variants. This is exploratory: every AIT
campaign and the existing CAM diagnostic have already been inspected. New
software does not turn them into an independent confirmation set.

## Fixed implementation and selection

* Preserve eight outer folds: six fitting, next campaign validation, one test.
* Availability is an explicit input supplied by the source configuration or
  controlled removal experiment. An absent detector is not a zero-alert
  detector. Fit experts for all seven nonempty subsets of AMiner, Suricata,
  Wazuh. No-sensor input produces an abstention, not a safe/zero-risk assertion.
* Unit 1: fit stage-parent / detector-count-child BN conditional likelihoods
  on fitting campaigns. Omit absent children from likelihood computation.
  Apply a fixed likelihood power 1/sqrt(number of available count columns);
  disclose this as approximate tempered evidence, not a new inference method.
* Unit 2: forward geometric-HMM stage filtering with fitted transitions; no
  smoothing, retrospective Viterbi or test labels. Each fitting campaign's
  state features use an HMM fitted to the other five fitting campaigns, with
  count bins fitted only there. Full six-campaign HMM supplies validation/test
  state features. State posterior and trailing 5/15/60-minute means augment
  the original causal detector-count summaries.
* Fit two tree families: availability-specific counts only, and counts plus
  BN/HMM state summaries. Preserve the original boosting configuration and
  seed. Retain every variant and sensor subset; audit splits that use state
  features to distinguish execution from actual predictive use.
* Third variant: one shared blend coefficient across horizons from
  {0, .25, .5, .75, 1}, where 0 means counts-only and 1 state-augmented.
  Calibrate each candidate on validation only. Minimize mean validation Brier
  normalized by target prevalence variance, plus .01 times the state weight;
  ties favor counts-only. A baseline fallback guarantees nothing on test.
  Calibration and blend selection share the validation campaign; disclose
  this limitation. A zero weight does not prove useful HMM contribution.
* Unit 3: retain the onset-distribution/action-delay expected-utility Decision
  Network; rerun its 27 damage/effect/disruption settings for all candidates.
  Match the original damage {10,20,50}, effect scales {.5,.8,1}, disruption
  scales {.5,1,2}; regenerate utility records from frozen forecasts if needed.
  Costs and intervention effects remain assumed; no real prevention is claimed.

## Evaluation

* Calibrated and raw Brier/AP for all six horizons; original permissive and
  strict new-warning metrics. Primary interpretation uses timely new warnings.
* Strict validation-selected thresholds at budgets 0/.25/1/4 false episodes
  per 24 negative hours, retaining at most five negative warning minutes.
  Frozen thresholds, unchanged target clock. Both scheduled and audited root
  outcomes on AIT, plus availability-delay sensitivity at 0/1/2/5 minutes.
* Natural full-sensor performance, each one-sensor removal, and remaining
  nonempty subsets. Compare with both the original zero-filled outage method
  and the new counts-only expert. Modified traces are paired stress conditions,
  not new independent campaigns. Known availability is an assumption until
  collection heartbeats/receipt timestamps are measured.
* Reuse the fox fold, AIT-only fitting vocabulary and selected validation blend
  for CAM with explicitly declared Wazuh/Suricata availability. No CAM tuning.
  Existing three targets are executed-tactic proxies, not validated success.
  Source-domain and detector differences may still defeat transfer.
* Report campaign dependence, remove-wheeler sensitivity, pairwise differences,
  AP/Brier tradeoffs, actual state weights and feature usage. Do not select the
  winning variant based on test scores or overwrite the previous evidence.
* Additional context controls were specified while the fixed primary run was
  completing, before its full result analysis. On natural full-input folds,
  train elapsed-time-only boosting and original count summaries extended with
  trailing 180/360/1440-minute means plus elapsed time. Use the same fixed
  estimator/calibration/strict-budget protocol. These controls are not part of
  blend selection: they test whether state-model gains exceed simple clock or
  longer-history information. They remain exploratory comparators.

Outputs: `experiments/robust_forecasting`. Preserve original experiments.
Independent tests must check prefix causality, absent-input invariance, fitting
split isolation, blend selection, saved-score consistency, abstention and
Decision Network onset/delay arithmetic. Raw source datasets are unchanged.

Fresh independent campaigns, measured online detector availability and real
comparative defensive runs remain separate evidence requirements. The current
offline experiment cannot eliminate those limitations or prove publication.

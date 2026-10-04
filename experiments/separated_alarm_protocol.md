# Second revision: keep forecasts and state-confirmed alarms separate

The first fixed revised state-feature/blending run completed with worse natural
15/30-minute Brier and lower 15-minute timely coverage. Those results remain
saved. This second revision was specified after that exploratory finding;
it is another development round on already inspected campaigns, not confirmation.

* Reuse the availability-specific count forecaster's frozen calibrated
  probabilities. Do not alter probability outputs using an HMM gate. Brier/AP
  therefore equal that predictor by construction; this is preservation, not
  new probabilistic forecasting accuracy.
* Unit 1 and Unit 2: fit the same count-likelihood BN / tempered forward HMM on
  six fitting campaigns. State belief mass in the last two stages provides an
  alarm-confirmation signal. No smoothing or target labels at prediction.
* For each horizon and validation alarm budget, consider confirmation levels
  {0,.5,.9}. Zero disables confirmation. Select the risk threshold for each
  level using validation only; prefer timely warning coverage, lead, lower
  negative warning duration and fewer false episodes. Exact ties favor zero
  confirmation. Frozen selections apply to test; no test outcome chooses a
  gate or risk threshold.
* Alarm-score masking uses -1 only to represent an ineligible alarm minute;
  it is never a probability. Maintain probability arrays separately. No-sensor
  input remains an explicit abstention; static availability is assumed known.
* Unit 3: keep the same onset-CDF/action-delay Decision Network. In a separate
  assumed policy replay, execute its chosen action only while the selected
  30-minute alarm policy is active; otherwise Monitor. Compare delay-aware and
  delay-blind choices under the same gate. Actual utility remains unmeasured.
* Evaluate all seven availability subsets on all eight AIT folds; both scheduled
  and audited root endpoints; all six horizons and four budgets. Compare the
  ungated count expert and original fusion under identical strict policies.
  Reuse the AIT fox fit/validation for the same three CAM proxies without tuning.
* Report gate values, actual changed warning minutes, saved probability equality,
  false episodes, missed targets, removal of wheeler and baseline controls.
  A gate of zero or an unchanged alarm trajectory is not evidence of helpful
  HMM confirmation. Negative first-revision results are never overwritten.

Outputs are under `experiments/robust_forecasting`, prefixed `gate_` or `gated_`.
Fresh independent campaigns, source receipt times and executed defense remain
unresolved data requirements. Improvement over older fusion is not proof of
improvement over the unchanged boosting probability model or exact novelty.

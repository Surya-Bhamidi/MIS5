# Evidence-association pilot protocol

Written before outcome scoring, 4 October 2026. This is an exploratory pilot,
not a preregistered confirmatory study or a completed novelty assessment.

- Inputs: public AIT-ADS eight simulated scenarios, separately downloaded and
  checksum verified. Existing DARPA experiments and database remain separate.
- Endpoint: first scheduled privilege-escalation start, provided its position
  after reconnaissance and webshell in the supplied labels is validated.
  This is a scheduled-stage forecast pilot, not proven DDoS prediction or
  demonstrated successful attack prevention. Exfiltration is excluded because
  published onset ordering was inconsistent in six scenarios.
- Causal observations: only sensor records timestamped at or before the
  evaluation time; phase labels, scenario names, filenames, and attacker IP
  identity are excluded from model features. Identity fields may support
  within-window association, not classification of attack state.
- Clock: 60-second intervals. Predict onset within 5, 15, and 30 minutes.
  Do not use target/post-target observations to score pre-onset forecasts.
- Split: leave one scenario out for testing, a second scenario for calibration,
  and the remaining six for fitting. Scenario variants stay in their fold.
- Shared forecaster: discrete threat-state HMM with count-likelihood Bayesian
  observation model and transitions learned only from fitting scenarios.
- Compare: separate-report likelihood; exact-record deduplication; content/time
  deterministic event grouping; probabilistic association of candidate pairs.
  Also a simple direct future-outcome baseline where data permits.
- Exact replays must change neither clock nor the deduplicated model's results.
  Include them as a correctness check, not as evidence of superiority over
  ordinary deduplication.
- Association prototype: bounded disjoint pairs of matching report categories
  within one clock interval. Sum over shared/distinct-event count hypotheses;
  do not simply multiply a second posterior into the HMM. No claim of global
  optimal multi-event association. Matching parameters use fitting data only.
- Natural traces are the main comparison. Controlled alias/jitter report copies
  are supplementary stress conditions. They preserve attack onset, are applied
  equally to all methods, and retain hidden origin IDs only for transformation
  ground truth. Genuine independent similar records must not be treated as
  known duplicates without provenance.
- Primary warning comparison: episode warning recall at a validation-selected
  false-warning budget. Report lead time and misses, false-warning episodes per
  benign/exposure hour, and horizon Brier/PR-AUC. Provide uncalibrated and
  independently calibrated comparisons where feasible.
- Any response utility uses the same stated loss/cost model for all forecasts.
  It is hypothetical policy evaluation, not measured prevention.
- Eight scenario outcomes give limited uncertainty and related attack chains.
  Replays and noise seeds do not create independent campaigns. Report every
  fold and negative results; do not infer academic originality from a gain.
- Model settings may need corrections following schema/correctness checks.
  Document changes made after initial scoring and treat them as exploratory.

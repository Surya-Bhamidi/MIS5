# Supplemental publication validation (2026-10-04)

This is exploratory follow-up to the completed AIT/DARPA experiments. All eight
AIT outcomes have already informed development; none becomes an independent
confirmation by being split differently. Existing model settings, predictions,
calibration and warning thresholds remain frozen for the endpoint audit.

1. Verify scheduled AIT privilege-escalation onset against original attacker
execution logs and attack-labelled victim audit records. Require successful
USER_START session records for the change-user endpoint; separately require a
successful root session for the stronger root-access endpoint. Labels select
attack-related records for evaluation only; these logs never enter features.
Report missing evidence, offsets and the resolution of timing assumptions.
2. Rescore saved forecasts against both observed endpoints, with the original
validation-selected thresholds. Report both any-warning coverage and strict
coverage requiring a NEW warning episode to start within the forecast window.
Evaluate synthetic forecast availability delays of 0, 1, 2 and 5 minutes with
no threshold adjustment; this is sensitivity analysis, not measured latency.
3. Add a clearly identified adaptation of Perera et al. (2016), arXiv:1610.07276:
10 k-means observation clusters and an 8-state unsupervised categorical HMM
trained by Baum-Welch. Use the same minute-clock detector counts and fitting-only
vocabulary as other methods (rather than their per-alert IP/port bag of words).
Use both prefix-Viterbi last-state and filtered-state projections. Attach an
explicitly new fitting-only target-onset hazard to convert next-alert prediction
into clock-time first-onset forecasts. Therefore this is not a reproduction of
the paper's Snort accuracy. Fixed seed 1729, 25 EM iterations, pseudocount 0.01,
full KMeans n_init=3, at most 10,000 evenly sampled fitting bins. No grid search.
Use the original 6-fit/1-validation/1-test folds and the same calibration/threshold
procedure. Preserve every result, including weaker adapted baselines.
4. Add a bounded GRU baseline inspired by Ansari et al. (2022),
DOI:10.1016/j.future.2021.09.040. Preserve three stacked GRU layers followed by
a dense prediction head, but use count inputs and six first-onset outputs;
this is explicitly an adaptation, not a reproduction of Warden next-alert
results. Fix 32 hidden units, a 30-minute past window, Adam learning rate 0.001,
six epochs, batch size 128, seed 1729, zero dropout. Fit standardization on
fitting runs only; retain every fitting bin within 30 minutes of onset and at
most 10,000 seeded negative bins. Use square-root inverse-prevalence BCE weights
computed on this fitting subset. Do not tune on outer test campaigns.
5. Inspect CAM-LDS original archives for an untouched external transfer set.
Select one variant of each of its six distinct scenario templates before outcome
scoring. Never use attack-filtered manifestations as background evidence. Do not
claim independent repetitions from variants sharing a scenario. If source streams
or endpoints cannot support a fair causal test, document the exact incompatibility.
For a bounded external diagnostic, freeze the AIT fox fold (six fitting campaigns,
harrison calibration campaign), its learned fusion coefficients and alarm
thresholds. Refit its base models with unchanged settings and verify harrison
predictions against saved predictions before transfer. Apply those models to
complete CAM Wazuh streams without retraining, synthesizing AMiner, or using CAM
outcomes for thresholds. Use the first executed step whose published tactic
contains Privilege Escalation as a proxy endpoint; exclude templates without that
annotation from warning recall and record their exclusion. This is a missing-
sensor/domain-shift diagnostic on an execution proxy, not independent confirmation
of successful-outcome performance of a full three-sensor pipeline.
6. Publish full per-campaign results and a manuscript draft with substantive BN
inference (Unit 1), HMM/duration modeling (Unit 2) and expected-utility Decision
Network (Unit 3). The response model has assumed costs/effectiveness, and no
prevention benefit may be inferred from forecasting alone.

No state-of-the-art, first-ever combination, or acceptance guarantee is asserted.

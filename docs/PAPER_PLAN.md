# Concrete route from the project to a research paper

**Current work boundary:** freeze the fixed .25 state blend for the 30-minute
research use case; defer further advancements. [CURRENT_VERSION.md](CURRENT_VERSION.md)
defines the preset and [the frozen package](../experiments/current_version/README.md)
preserves its predictions, calibrators and thresholds. All earlier experiments
and the failed adaptive primary target remain part of the evidence.

**Latest completed follow-up:** [selective fusion report](../experiments/selective_fusion/REPORT.md)
contains all six fixed variants and 33 passing tests. A prespecified fixed
.25 state blend gives a conditional 30-minute warning/probability gain, and
selective fusion helps with Wazuh absent against matched pooled counts. Its
full-input 15-minute primary target fails and external warnings remain absent.
The empirical question is now which horizons/availability conditions benefit
from probabilistic stage information, and which tradeoffs remain after
campaign-based calibration. Fresh confirmation remains necessary; do not
claim first-ever architecture or replace a failed primary result silently.

**Most recent completed evaluation:** [revised forecasting report](../experiments/robust_forecasting/REPORT.md)
retains all availability-specific, BN/HMM feature, blend, clock/history control
and confirmation results. Availability routing recovers useful missing-Wazuh
warnings through counts-only experts. BN/HMM features yield conditional gains
at a higher false-alarm/probability-error cost and worsen full-input 15-minute
performance. Validation disables the confirmation branch at the primary
horizons. The contribution cannot be described as universal improvement from
the model combination. Fresh independent evaluation and real response-effect
evidence remain required for stronger claims.

**Latest evaluation:** The expanded detector/packet study and learned forecast
fusion now provide a more concrete empirical direction. See the
[complete extended results](../experiments/extended_study/REPORT.md) and
[paper specification](PAPER_SPECIFICATION.md). Some warning tradeoffs improve;
there is no universal superiority or verified original algorithm. The older
association hypothesis and its negative results below are preserved as history.

Prepared 4 October 2026. Recommended direction: a focused methods and empirical evaluation paper on evidence dependence in early cyberattack forecasting. This plan specifies a candidate contribution; neither originality nor performance improvement is established. See [NOVELTY_AUDIT.md](NOVELTY_AUDIT.md) for known precedents and [RESEARCH_PIPELINE.md](RESEARCH_PIPELINE.md) for the forecast architecture.

**Publication validation update:** The implemented follow-up verifies successful AIT victim-side sessions, adds strict new-warning scoring and published-method HMM/GRU adaptations, and records a negative external transfer diagnostic. Read the [supplemental report](../experiments/publication_validation/REPORT.md) and [manuscript draft](PAPER_DRAFT.md) for the current evidence and narrow paper claim. Unit 1 BN inference, Unit 2 HMM modeling and Unit 3 Decision Network are all substantive components. Broad first-ever/superiority claims remain unsupported.

**Pilot update, 4 October 2026:** An isolated association-mixture prototype was evaluated on all eight AIT-ADS scenarios with six fitting, one calibration, and one test scenario per fold. Results are mixed and do not establish superiority: natural-trace calibrated Brier is worse than exact deduplication at all three horizons, and there are no additional successful 15-minute warnings under the tested rule. Ranking improves under constructed alias/jitter copies, but genuine event identities remain unvalidated. The endpoint is scheduled privilege escalation, not DDoS. See the [complete pilot results](../experiments/evidence_pilot/REPORT.md), including every baseline, negative result, and limitation. This remains a research hypothesis rather than a demonstrated novelty claim.

## Recommended paper question

**Combination check:** Additional same-data comparisons found that the present BN-HMM observation/filter construction is equivalent to a conventional factorized categorical HMM. Temporal filtering improves ranking over its no-filter ablation but does not yield useful 15-minute warnings under the tested rule. No complete named published forecasting system has been reproduced on the pilot task; incompatible published accuracy/F1 scores cannot establish superiority. See the [component and literature comparison](../experiments/combination_comparison/REPORT.md).

**Can distinguishing replayed reports, shared-event observations, and independent evidence improve pre-onset forecasts and response choices compared with ordinary alert deduplication?**

Working title: **Evidence Dependence in Early Cyberattack Forecasting: A Bayesian Temporal Model and Decision Study**.

Retain the aim of predicting a harmful outcome before its occurrence. Initially forecast DDoS launch from preceding activity in DARPA. For a second benchmark, choose and validate a separately named outcome from a modern multi-stage dataset. Earlier malicious precursors may already have happened; the outcome being forecast must be explicit.

## Candidate methodological addition

Extend the BN observation model with latent underlying-event and report-association variables. Sensor reports that may describe the same action share a possible latent event. Sensor-specific observation/reliability variables represent uncertainty in the measurements. Account for ambiguous associations instead of always merging or always treating reports as separate events.

There are four distinct cases to model:

| Case | Intended treatment |
|---|---|
| The same stored sensor observation is replayed | Process once; preserve an audit record of replays. |
| Multiple sensors observe one real action | Model a shared event and sensor errors. Additional independent measurement can corroborate that event. |
| Two genuine actions look similar | Preserve both actions; similarity alone must not erase repeated behavior. |
| It is uncertain whether reports share an event | Marginalize over possible associations in the observation model. |

For a bounded candidate group, the BN can sum over shared-event and distinct-event explanations to obtain the likelihood of the reports given the threat state. Begin with small groups to keep inference tractable. Specify a complete joint probability model: matching scores derived from the same alert fields must not be multiplied as another independent likelihood. If sensor errors share a cause, conditional independence given the event alone is insufficient; include the dependence or evaluate the simplifying assumption.

The HMM uses that likelihood once at a fixed clock interval. It estimates latent stages and projects first-onset risk. The Decision Network evaluates actions using forecast outcome probabilities, costs, and declared action-delay/effect assumptions.

This is more specific than adding a generic deduplication step, but latent-variable modeling and probabilistic association are established principles. Its precise novelty still requires comparison with the closest alert-fusion and dependent-sensor methods after the model is specified. The empirical question can remain valuable even if the inference construction is conventional.

| Syllabus unit | Substantive component |
|---|---|
| Unit 1 | Bayesian Network inference over underlying events, report associations, and sensor evidence. |
| Unit 2 | HMM filtering and future-onset projection on a defined clock grid. |
| Unit 3 | Decision Network selecting responses using forecast risks and operational costs. |

## First milestone: trustworthy forecasting before the new method

1. Remove `true_phase_label` from signature construction and all model inputs. Keep labels exclusively for training targets and evaluation. Review filenames and address-specific boosts for other shortcuts.
2. Make sensor co-occurrence causal. The current normalizer compares against the entire sorted trace, including later records within its time tolerance. A forecast at time t may only use records received by t. Later evidence must not retroactively alter earlier reported forecasts.
3. Replace event-count progression with a fixed clock grid; compute equivalent feature windows for every compared method. Learn parameters from training episodes only.
4. Generate future-onset labels from an independent annotation table. Score only pre-onset timestamps and handle incomplete follow-up explicitly.
5. Establish ordinary deduplication plus coherent BN-HMM as the main baseline. Fixing leakage or an incorrect filter is necessary groundwork, not evidence that the new observation model is better than a sound baseline.

Relevant existing files: `backend/app/ingestion/normalizer.py`, `backend/app/models/bayesian_network.py`, `backend/app/models/hmm_model.py`, `backend/app/models/pipeline.py`, and `backend/app/evaluation/experiment_runner.py`. The extended study subsequently removed phase-label dependence and future-event contamination in the normalizer and added regression tests. The research engine is separate; cached dashboard data and its heuristic forecast model are not validated paper evidence.

## Dataset plan and an annotation issue found during inspection

Use the two DARPA scenarios for debugging and a DDoS case study. Their thousands of alert rows represent only two scenarios and contain inadequate benign exposure in the currently ingested tables. Recover background telemetry and do not claim generalization from random alert-row splits.

The [AIT Alert Data Set](https://zenodo.org/records/8263181) is a practical additional candidate: eight scenarios, three IDSs, background false positives, phase labels, and a 96.2 MB compressed archive. Its outcomes include exfiltration and stopped service; it is not a DDoS benchmark. Underlying logs and independent attack-step execution records are available in the [AIT Log Data Set V2.0](https://zenodo.org/records/5789064).

**Endpoint ordering audit update (4 October 2026).** The original concern was that `dnsteal` and `service_stop` start before `network_scans` in six scenarios. The dataset's attack description treats DNSteal as a separate attack active from simulation start; the retrieved attacker logs contain its later `dnsteal_stop`. This is not a reason to reorder labels into a scan-to-exfiltration chain. Preserve the published annotations and use the verified scan/webshell/reverse-shell/privilege sequence for this target. Original attack-labelled victim audit logs now confirm successful change-user sessions in all eight campaigns, 0.779–2.403 seconds after scheduled escalation. Root sessions occur 12.056–27.243 seconds after scheduled escalation and are separately evaluated. See [the auditable endpoint evidence](../experiments/publication_validation/endpoint_evidence.json). These records are evaluation evidence only, never model inputs.

A documented endpoint such as webshell deployment or privilege escalation could support a separate forecast task if its timing and meaning are validated. Forecasting that outcome is distinct from DDoS forecasting. If DDoS must be the sole endpoint, collect additional independently executed DDoS campaigns with benign-only and aborted runs. AIT's eight related scenarios provide a useful pilot, not evidence of broad attack-family generalization.

Event identity also needs ground truth. Controlled report replays provide exact known duplicates, but real cross-sensor same-event associations may require raw provenance or manual annotation. Attack-phase labels are not event-identity labels. Do not manufacture identity truth merely by applying the same heuristic being evaluated.

## Minimal comparison that isolates the contribution

Give every method identical past-only inputs, forecast labels, training/calibration/test episodes, clock timestamps, and tuning opportunities.

| Method | Why it is needed |
|---|---|
| Direct logistic or tree-based future-outcome predictor | Tests whether a simple supervised forecaster already solves the task. |
| BN-only and HMM-only forecasts | Tests the value of combining models. |
| Coherent BN-HMM with no report consolidation | Measures sensitivity to overlapping/replayed evidence. |
| Coherent BN-HMM with ordinary deterministic deduplication | Main practical comparator; tests whether a simple correction is enough. |
| Reliability-aware BN-HMM with deterministic event grouping | Separates sensor reliability from uncertain event identity. |
| BN-HMM with the proposed latent-event observation model | Tests the specific addition. |
| Relevant published alert-fusion/prediction implementation | Establishes external comparison where method details allow reproduction. |

Apply the same Decision Network to competing forecasts, then compare the selected forecast with a simple forecast-threshold response. This separates forecast gains from decision-policy differences. Present-state response can be an additional baseline.

## Experiments and what counts as improvement

Evaluate natural traces first. Then stress each held-out episode with prespecified exact report replays, cross-sensor overlap, genuine repeated actions, ambiguous matches, sensor disagreement, delayed arrivals, and missing telemetry. Do not add synthetic reporting noise only to competitors. Preserve event-time ground truth, distinguish event time from receipt time, and score everyone at identical clock timestamps.

Match transformations to the failure being tested. Dropping a report removes an observation, not the underlying attack. Repeating a genuine request changes the underlying behavior and must not be mislabeled as a replay. Validate realistic perturbation ranges on training data and report performance across levels rather than selecting only favorable stress conditions.

Use episode-level warning recall at a fixed false-warning budget as the primary metric. Report the threshold-selection procedure and benign exposure. Supporting outcomes are warning lead time with coverage of missed attacks, horizon Brier scores/calibration, false-warning episodes per benign hour, unnecessary Block/Isolate decisions, and computational cost.

Split by campaign/scenario; keep all transformed versions of an episode within its split. Fit calibration and response thresholds using training/validation data. Resampling many alerts or replaying one campaign with many seeds does not create independent attack episodes. Use run-level comparisons and report the uncertainty caused by small sample sizes.

An improvement need not be a higher accuracy percentage. Earlier warnings at the same false-warning rate, lower false-warning rates at comparable warning coverage, or lower response disruption under common cost assumptions can be meaningful results. Decision utility from passive logs remains conditional on modeled effects; claim measured prevention only when actions and outcomes have been evaluated in an executable testbed.

## Decision points before writing the final claims

- If deterministic deduplication fixes the observed failure and the proposed method adds no benefit, do not claim a superior algorithm. Investigate the operating conditions or narrow the work to a reproducible empirical finding.
- If benefits occur only under artificial report replication, frame that result narrowly and obtain realistic overlap evidence before general claims.
- If gains persist against sound baselines across independent held-out episodes, quantify the gain and its tradeoffs. Recheck related work against the actual implemented mechanism.
- If endpoint validation or benign data is inadequate, resolve the dataset issue before publishing forecast numbers.

Potential contribution wording, to use only after results support it:

> We evaluate an event-dependency observation model within a Bayesian temporal forecasting system and show when accounting for uncertain shared evidence improves pre-onset warning reliability and response choices relative to deterministic deduplication.

Release preprocessing, endpoint annotations/corrections, split manifests, perturbation code, model specifications, configurations, and result-generation scripts. Select the submission venue after the study's evidence and scope are clear. Paper acceptance is not guaranteed by a pipeline name or a target accuracy.

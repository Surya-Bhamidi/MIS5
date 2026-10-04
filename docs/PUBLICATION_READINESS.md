# Current paper scope and evidence gaps

**Current research preset:** the fixed .25 state blend is frozen for the
30-minute use case. See [CURRENT_VERSION.md](CURRENT_VERSION.md) and
[the frozen artifacts](../experiments/current_version/README.md).
Further advancements are deferred at the user's request. This development
choice does not replace the failed adaptive primary result or establish a
model that is best across all horizons and conditions.

The newest [selective fusion experiment](../experiments/selective_fusion/REPORT.md)
is complete: 33 tests and independent checks cover nested fitting, weights,
calibration, alarms and decisions. A prespecified fixed .25 state blend gives
5/8 timely 30-minute root warnings versus 4/8 for original calibrated counts,
4.25% lower Brier and five versus 19 aggregate false episodes. This is a
conditional positive result: excluding wheeler reverses the false-episode
gain, AP is slightly lower, and matched pooled counts has fewer false episodes.
The adaptive selector's 15-minute primary result is 5/8 warnings at 17 false
episodes and higher Brier, failing the stated operational target. Without
Wazuh, selective fusion gives 3/8 versus 2/8 warnings for matched pooled counts
at one false episode each, with 3.13% lower scheduled-onset Brier and better AP,
but longer negative warning duration. These results support a narrow empirical
tradeoff study using substantive BN/HMM/Decision Network components; they do
not establish massive general improvement. All new external 15/30-minute
proxy warnings remain 0/3. Earlier experiments below remain in the record.

The [completed improvement analysis](../experiments/robust_forecasting/REPORT.md)
adds explicit sensor availability, cross-fitted BN/HMM stage features,
longer-history/clock controls and a probability-preserving alarm revision.
All 28 tests pass. The software distinguishes missing sensors from observed
zeros and abstains with no sensors. With Wazuh missing, the availability-specific
counts policy recovers 3/8 timely warnings at one false episode versus zero old
warnings; this is a counts-policy gain. Without AMiner, BN/HMM features recover
2/8 versus 0/8 for the matching counts expert, but false episodes rise from 3
to 13. Full-input 15-minute coverage deteriorates from 4/8 to 2/8 with 15 rather
than 3 false episodes and approximately four times the Brier error. At 30
minutes, coverage stays 4/8 and false episodes fall from 19 to 7, with worse
probability error. The second revision selects no HMM confirmation at either
primary horizon for any availability subset or tested budget. External
15-minute warnings remain 0/3; state features produce 1/3 warnings at 30
minutes, but short proxy-outcome recordings cannot validate the alarm budget.
Consequently the new experiments do not remove
the main generalization or full-combination performance gaps.

The completed work supports an **exploratory empirical manuscript**, available
in [PAPER_DRAFT.md](PAPER_DRAFT.md), with an auditable
[supplemental report](../experiments/publication_validation/REPORT.md).
It does not establish that the architecture is previously unpublished or that
the complete pipeline outperforms existing published systems.

The [additional comparison report](../experiments/published_comparison/REPORT.md)
now includes eight longer-trained, validation-selected GRU folds and four
validation-selected alarm budgets across 15 model variants. At a tighter
30-minute budget, fusion loses timely coverage versus boosting at equal false
episode totals. The source-audited PARD-SSM author snapshot does not supply a
compatible complete predictive experiment; it is excluded from superiority
claims. These completed checks narrow the empirical claim; they do not remove
the need for fresh full-input campaigns or compatible full-system reproduction.

| Requirement | Evidence now available | Remaining limitation |
|---|---|---|
| Unit 1 | BN detector likelihood and conditional inference | Conditional independence is an approximation |
| Unit 2 | Causal HMM/duration filtering and first-onset risk | Related scenario templates; stage mappings need external validation |
| Unit 3 | Delay-aware expected-utility Decision Network | Assumed costs/effects; no demonstrated prevention benefit |
| Successful target | Original attack-labelled victim sessions in all eight AIT campaigns | Online availability of source alerts is not proved |
| Competitive comparisons | Common-split component, feature, HMM and GRU adaptations | Adaptations are fixed-budget comparators, not optimized full paper reproductions |
| Warning improvement | Root-case 30-minute false episodes 20 → 5 at equal 4/8 timely coverage | Excluding wheeler reverses the gain; Brier worsens |
| Multi-sensor improvement | 30.3% lower 15-minute Brier than best single-sensor tree | Five-minute ranking/coverage favors AMiner alone |
| Sensor availability | Seven availability-specific experts; missing evidence omitted; no-sensor abstention | Static declared availability only; state branch increases false alarms in some outages |
| Independent data | Six-template CAM source audit; frozen transfer on three eligible proxies | Previously inspected diagnostic, no warnings, missing AMiner and short exposure |
| Reproducibility | Saved forecasts, per-campaign scores, endpoint proofs, hashes, scripts and tests | Legacy application outputs remain separate from research evidence |

The contribution to present is **endpoint-audited, horizon-dependent findings
about multi-sensor forecasting and alarm/probability tradeoffs**. Include the
negative results; the model names alone are not the novelty.

For a stronger generalization claim, the next experiment should collect or
derive complete detector streams on new independently generated campaigns,
with documented detector training cutoffs, receipt timestamps and successful
target evidence. Freeze the model-selection process before inspecting those
test outcomes. Obtain long no-target intervals for evaluating false-alarm
budgets and at least several distinct attack templates. The necessary sample
size depends on the smallest improvement to be detected and must be planned
at campaign level, not inferred from millions of alert rows.

If new data require deriving missing detector streams, that needs their actual
configuration and causal training procedure. Filling missing inputs with
fabricated alerts or rearranging unrelated attack steps cannot validate this
pipeline. CAM includes Wazuh and Suricata alerts, but lacks AMiner. The available
stream has already been tested as a genuine
missing-input diagnostic and its negative result must remain in the record.

Before submission, select the venue and align manuscript length, references,
data/code licensing and required artifact format with its author instructions.
Add the actual authors and affiliations. Acceptance remains a reviewer decision;
a measured improvement is evidence for a contribution, not a guarantee.

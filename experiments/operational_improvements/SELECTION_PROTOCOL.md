# Validation selection protocol

Freeze this protocol before running the new comparison. The existing eight AIT
campaigns have already been inspected, so results remain development evidence.
No independent test-set or flawless-performance claim is permitted.

Forecast models, calibration, sensor experts, horizons and original validation
thresholds remain fixed. Compare eleven warning policies: immediate original
threshold behavior; immediate warnings with 60/120/300-second notification
cooldown; the previous two-bucket confirmed policy; and two-bucket confirmation
with immediate bypass at 1.25/2/4 times the original threshold, each with zero or
300-second notification cooldown. Fast paths use only current calibrated risk.

For each original fold, sensor subset and horizon, policy selection receives
only the archived outer-validation forecast, that validation campaign's verified
endpoint, and the frozen threshold. It never receives outer-test predictions,
labels or scores. The threshold was originally selected on this validation
campaign, so policy selection reuses validation data; this is not an additional
independent validation split.

A candidate is eligible only if validation notification and warning-episode
coverage and first timely lead are no worse than immediate threshold behavior,
and false notifications, false warning episodes, negative warning minutes and
total notifications do not increase. If immediate validation behavior has no
timely notification, retain the original policy: that campaign cannot establish
that a suppressive policy preserves responsiveness.

Among eligible policies, minimize false notifications, then false warning
episodes, then negative warning minutes, then total notifications; break ties
in favor of the original/simpler candidate order. Record every candidate and
guardrail outcome. Never choose policies by campaign name at inference time.
The local model package supplies the fixed fold's availability-specific selected
policy; live inference switches policy only when sensor availability changes.

After all choices are frozen, evaluate outer-test campaigns once and retain
every gain and regression. Compare with original and previous confirmed policy
on all seven sensor subsets at 15 and 30 minutes. Report each campaign's lead
change, raw visible risk, and notification suppression separately. Results cannot
establish that any candidate is best on every future metric.

# Audit of the requested future improvements

The confirmed-policy findings below are retained as the initial audit record.
The current default is responsive, and confirmed behavior is optional. Read
[the current release](CURRENT_RELEASE.md) for runtime defaults and optimization.

The code, comparison definitions, archived forecasts, runtime behavior and
documentation were audited separately. Verification is reproducible with
`python backend/research/audit_operational_improvements.py`; machine-readable
results are in `audit.json`.

| Requested improvement | Verified outcome | Status and limits |
|---|---|---|
| Reduce unnecessary alarms | At 30 minutes with all sensors: false notifications 5 to 2, false warning-state episodes 5 to 2, total notifications 14 to 8; the same five of eight campaigns receive timely notifications | Implemented and verified on inspected archived campaigns. Brier score is unchanged. This does not establish benign-traffic false-positive reduction or statistical superiority. |
| Strengthen operation with missing sensors | Automatic selection of all seven existing experts; missing/stale heartbeat handling; no-sensor abstention; recovery and skipped-bucket history resets; streaming/batch agreement | Runtime behavior is implemented and verified. The quoted Brier gains are existing experts versus a naive zero-fill comparator on fox, not a new trained-model gain over the original correctly selected experts. Accuracy on fresh dynamic outages remains unverified. |
| Test live warning latency and response effectiveness | Running local HTTP service, 180 archived observations, current-time input smoke check, persisted response receipts, and latency instrumentation | Partially fulfilled. No production sensor feed, independent live campaign, or defensive actuator was connected. Actual response/mitigation effectiveness remains outstanding. |

## Interpretation corrections

* A false notification means one sent more than the selected horizon before the
  recorded target outcome. It may occur during real earlier malicious activity.
  It is not necessarily a benign false positive.
* Campaign warning coverage of 5/8 is not 62.5% classification accuracy.
* Lower notification counts do not imply more accurate probabilities. The new
  warning layer does not change forecasts or their Brier error.
* The 15-minute full-sensor diagnostic loses coverage, from 4/8 to 3/8. At 30
  minutes, four of the five warned campaigns receive their first timely
  notification later, including a ten-minute delay on fox. Harrison improves
  enough to raise the mean lead by 0.6 minutes. That mean is not evidence of
  universally faster warnings.
* Existing sensor experts match their original frozen predictions exactly. The
  Brier reductions of 90.8%, 30.0% and 74.5% with one missing sensor measure their
  advantage over naive zero-filling on fox. They do not quantify the benefit of
  newly learned weights. Suricata alone is slightly worse under this comparator.
* Availability handling covers the three declared sensor families. It relies on
  truthful collector health information and cannot infer silent partial data
  loss inside a sensor that still reports a healthy, complete bucket.
* The pre-optimization roughly 66 ms p95 HTTP latency measured a local single-client processing path.
  It excludes sensor collection, finalized minute-bucket formation and the
  confirmation interval. No earlier HTTP baseline supports a latency reduction
  percentage. The acknowledgment/completion test has one no-op receipt sample.
* The extension is active under `/api/live`. Frozen archive replay and the
  earlier DARPA event demonstration retain their original semantics.

## Defects fixed during this audit

1. Cooldown previously prevented a confirmed episode from becoming visible until
   a notification was allowed. It now limits notifications while keeping the
   warning active. A pending notification can be sent if high risk persists until
   the cooldown expires. Warning-state episodes and notifications have separate
   metrics and dashboard columns. The main 30-minute aggregate values remain
   unchanged after this correction.
2. Live input previously accepted buckets up to 120 seconds in the future. It
   now accepts finalized buckets from the past 120 seconds, allowing only one
   second of clock skew.
3. Individually finite detector counts could overflow when aggregated. Such
   requests now fail validation before updating temporal state.
4. Timestamp grid checks now agree between the API and stream model. Invalid
   timestamp or sensor selections are rejected before changing stream state.
5. Persisted notification payloads now include observation/receive times, mode
   and live finalized-bucket age. Historical replay is not assigned a misleading
   wall-clock warning age.
6. The HTTP benchmark now checks returned probabilities and modeled actions
   against batch inference, including during sensor transitions. UI verification
   refuses occupied ports so an older process cannot accidentally pass the check.

## Evidence checked

An independent batch implementation of warning confirmation, clearing and
notification cooldown reproduces all **112 campaign/sensor/horizon cases** and
all **14 aggregates**. Every original baseline agrees with the original score
tables. The seven loaded experts exactly reproduce frozen forecasts and use
unchanged calibrators; fitting excludes both the test and validation campaigns.

Changing-outage checks compare actual streaming results with separately rebuilt
batch prefixes. All seven sensor subsets, total outage, recovery, a skipped
bucket and deliberately poisoned unavailable-sensor values were checked. Maximum
probability discrepancy is zero. These are functional inference checks, not an
independent measurement of detection accuracy or attack prevention.

Current backend, frontend and browser verification status is recorded in
`verification.json`; runtime measurements are in `live_benchmark.json`. Existing
frontend lint warnings remain in earlier components.
The initial audit passed 54 tests and measured 65.81 ms p95 before optimization.
The current release passes 62 tests; its frontend builds and desktop/mobile
browser check passes. Current local HTTP p95 is 27.27 ms, and the paired median
inference computation reduction is 83.1%, with identical forecasts.

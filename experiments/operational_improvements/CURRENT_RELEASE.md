# Current verified runtime release

This release prioritizes original warning responsiveness, reduces redundant computation,
and makes the quieter alternative explicit. It does not claim a universally best model
or flawless production performance. Forecast weights, calibration and thresholds are unchanged.

## Active behavior

* `responsive` is the live default: immediate threshold warnings with no added confirmation or notification cooldown.
* `confirmed` is optional: two-bucket confirmation and bounded episode handling reduce notifications at the cost of possible delays or missed brief signals.
* All seven healthy expert histories remain available for sensor fallback. Only the selected expert computes a forecast.
* Missing/stale sensors route to the matching original expert; complete outage abstains. Model status validates package integrity.
* The validation-selected candidate remains research-only because it failed to preserve all measured lead constraints.

## Verified campaign results

| Horizon | Profile | Timely campaigns | False warning episodes | Notifications | Mean notification lead |
|---|---|---:|---:|---:|---:|
| 30 min | Responsive (default) | 5/8 | 5 | 14 | 19.18 min |
| 30 min | Confirmed (optional) | 5/8 | 2 | 8 | 19.78 min |
| 15 min | Responsive (default) | 4/8 | 4 | 9 | 6.99 min |
| 15 min | Confirmed (optional) | 3/8 | 3 | 6 | 7.43 min |

The responsive policy exactly matches original warning and notification traces in all 112 fixed-availability campaign/sensor/horizon cases.
The optional confirmed profile retains its 30-minute alarm benefit, but its first timely notification is later on four of five warned campaigns, including a ten-minute delay on fox.
At 15 minutes its coverage is lower. These are previously inspected campaigns, not independent confirmation.
“False” refers to the target time window and does not necessarily mean benign traffic. Brier prediction error is unchanged.

## Inference performance

A same-process paired comparison used 180 archived minute buckets and identical fitted experts:

| Measurement | Previous eager reference | Selected-expert computation |
|---|---:|---:|
| Median inference | 42.81 ms | 7.32 ms |
| p95 inference | 51.08 ms | 9.17 ms |

Median inference computation falls by **82.9%**, with exactly identical selected forecast probabilities. The comparison includes causal history updates; it excludes sensor collection and HTTP.

The separate running-service replay processed 180 observations with **38.19 ms p95 HTTP round trip**.
It used the responsive profile and recorded 5/5 notification receipts and 5 no-op completions.
These receipt counts and timings do not demonstrate attack prevention. The earlier HTTP run is preserved in `live_benchmark_pre_optimization.json`; differences between separate HTTP runs are not a controlled speedup estimate.

## Candidate selection and release decision

Eleven candidate policies were evaluated in 112 original fold/sensor/horizon settings. Choices used outer-validation forecasts and endpoints only, with fixed original thresholds.
Eligibility required no validation loss in coverage or first lead and no increase in false notifications, false warning episodes, negative warning minutes or total notifications.
The resulting selector had lead regressions in 4 subsequent evaluation settings and was **not promoted**. The default does not change behavior by campaign identity.
The candidate set and these campaigns have been inspected during development. Reusing the original validation campaign for threshold and policy selection is not a new independent split.
See `SELECTION_PROTOCOL.md`, `policy_selection.json` and `selection_verification.json`; every candidate and observed regression is retained.

## Quality checks and remaining limits

* Backend: 95 tests pass.
* Frontend: production build, lint (no warnings), desktop/mobile checks, replay controls and reordered-reply browser checks pass.
* Independent reconstruction: 112 campaign/sensor/horizon cases and 14 aggregates pass.
* All seven model experts match their frozen forecasts exactly; changing-outage stream/batch checks, poisoned unavailable input and recovery checks pass.
* The database connection leak found in verification is fixed; model readiness rejects missing, corrupt or unloadable packages.
* Sensor-error gains remain existing experts versus naive zero-fill on one inspected fold. Fresh-campaign dynamic-outage accuracy is not established.
* No production sensor feed or defensive actuator was connected. Real mitigation effectiveness, production load behavior and independent generalization remain unmeasured.
* Stream state is process-local and resets on restart. Source health must describe a complete collector path; a heartbeat cannot expose silent partial loss inside a sensor reported healthy.

For setup and profile selection, read [the runbook](../../docs/OPERATIONAL_IMPROVEMENTS.md).
The confirmed-profile study is retained in [REPORT.md](REPORT.md), with the original caveats.

## Thorough local validation and fixes

* All 56 refitted experts across eight campaigns reproduce 2,007,012 saved forecast values with zero error. Stream prefixes remain causal and test labels cannot affect inference.
* 1,152 API observations exercise all sensor subsets, stale/missing heartbeats, outages, recovery, gaps, extreme counts, unknown detectors and poisoned unavailable-sensor counts.
* 25,440 score rows, 3,660 aggregate rows and 8,064 threshold choices were independently reconstructed. Threshold optimality is restricted to the original declared validation grid and constraints.
* 65 frozen-package files retain their original checksums. Dashboard evidence is checked before content-keyed cache access; corruption or incomplete evidence produces a 503 instead of a stale verified result.
* Exact most-recent observation retries return the committed result and notification ID. Changed evidence at the same timestamp conflicts. Failed inference or notification persistence rolls temporal and warning state back so the bucket can be retried.
* The local API rejects remote peers, cross-site browser requests, forged hosts, ambiguous lengths, oversized/slow bodies and invalid schemas. Validation responses omit rejected values. This is a loopback research service, not production authentication.
* Legacy individual streams have separate client cookies; historical batches own independent state. SQL identifiers are allowlisted, generation is bounded, and an empty synthetic run replaces only its own rows. Legacy temporal history is bounded.
* Legacy action ranking now uses unrounded utility; an action compared with itself has identical illustrative loss curves. Both chart series use the same scale. Browser controls prevent stale scenario, mode, horizon or action responses replacing newer results.
* Live action costs account for forecast age within the original observation-based 30-minute window. Linear CDF interpolation between saved horizons is an explicit modeling assumption. Historical replay retains its original formula.
* Completed/failed receipts are immutable, retries preserve the first timing and notes, and backwards-clock receipts are rejected. Failed responses now have resolution timing.
* Model packages receive structural/probability checks after checksum validation. Pickle remains trusted local code: manifests are not signatures, and a hostile local writer is outside this protection.
* A narrow source scan found no matching private-key/API-key patterns outside excluded data and private folders. This is not an exhaustive credential or dependency-vulnerability audit.

## Costs and limits of the fixes

The final HTTP replay measured 25.52 ms median, 38.19 ms p95 and 375.88 ms maximum. It includes validation, transactional checkpoints and receipt persistence. Earlier separate runs are retained and are not interchangeable with this measurement; no end-to-end speedup is claimed.
The default still warns on 5/8 of these campaigns at 30 minutes. Suppressing more alarms can miss or delay warnings; complete sensor loss still requires abstention. Bounds intentionally reject excessive requests. Sessions and idempotency are process-local, and only the most recent observation has an idempotent replay cache; restart or multi-worker recovery is not implemented.
Response effects and monetary savings have not been observed. Existing cached legacy RQ reports may predate the corrected simulation and are labeled separately in the UI. Python emitted existing optional dependency/deprecation/core-detection warnings during checks; passing tests do not imply a warning-free environment or an exhaustive security assessment.
These tests establish the stated local properties. They cannot establish flawless behavior, a globally optimal architecture, or success against every future attack.

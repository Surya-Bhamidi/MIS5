# Operational improvement evaluation

This is the confirmed-profile study and pre-optimization local timing record.
The current live default is responsive; confirmed behavior is explicit opt-in.
See [the current verified release](CURRENT_RELEASE.md) for active defaults,
the inference optimization, and the rejected validation-selected candidate.

The new extension adds confirmed warning episodes, automatic sensor-health
routing, incremental inference, and persistent response receipts. It keeps the
original frozen forecast results intact. Results below are development evidence
from previously inspected campaigns, not an independent confirmation.

## Fewer unnecessary alarms

Paired replay uses identical probabilities and unchanged fold-specific validation
thresholds (budget 1). Only the warning policy changes: two consecutive minute
buckets confirm a warning; bounded hysteresis clears an episode; notifications
have a five-minute cooldown. No test-label threshold search is performed.
The operational policy was engineered during development on these inspected
datasets; this is not a preregistered policy evaluation.

| Full-sensor 30-minute result, eight campaigns | Original threshold | Operational policy | Change |
|---|---:|---:|---:|
| False notifications | 5 | 2 | 60% fewer |
| False confirmed warning episodes | 5 | 2 | 60% fewer |
| All notifications | 14 | 8 | 42.9% fewer |
| Campaigns with a timely new warning | 5/8 | 5/8 | Preserved |
| Negative warning minutes | 33 | 29 | 12.1% fewer |
| Mean Brier score | .001460568 | .001460568 | Unchanged |
| Mean lead over warned campaigns | 19.18 min | 19.78 min | +0.60 min |

"False" means a warning starts or a notification is sent more than 30 minutes
before the recorded successful-root outcome. Such periods can contain earlier
malicious activity. This is not a measured false-positive rate on independent
benign deployments. Coverage of 5/8 is campaign coverage, not overall accuracy.
Warning-state starts and outbound notifications are now scored separately;
cooldown suppresses notification traffic while confirmed warnings remain visible.

The same five campaigns receive timely warnings. Mean lead hides individual
delays: fox's first timely notification moves from 21.72 to 11.72 minutes before
the outcome. Confirmation requires one additional minute when two consecutive
crossings occur; short crossings can be suppressed altogether.

At 15 minutes, coverage decreases from 4/8 to 3/8 while false episodes decrease
from four to three. The new live service targets **30 minutes**. It does not
claim a universal improvement at 15 minutes or across sensor configurations.
Per-campaign and per-sensor results are in `evaluation.json`.

## Missing sensors

Live input declares sensor heartbeats separately from alert counts. A healthy
sensor with zero alerts is valid evidence. Missing or older-than-90-second
heartbeats omit that sensor and route to the matching expert and calibrator.
The service maintains all seven experts, resets affected histories after outages
or skipped minute buckets, and abstains if no sensors remain. A returning sensor
starts a fresh history; immediate post-recovery accuracy is not established.

The experts already existed in the frozen research version. The implementation
improvement is automatic streaming selection and history handling. It does not
represent a newly discovered forecasting architecture.
The reported Brier reductions therefore compare those existing experts with a
naive zero-fill comparator; they are not gains over the original framework when
its correct availability expert was already selected. All seven packaged experts
still exactly reproduce their original frozen forecasts.

The additional paired outage test holds the fox research fold fixed and compares
the availability expert with using its full-sensor model after zero-filling
unavailable inputs. These are **whole-campaign induced outages in one held-out
research fold**, not eight independent deployment trials. Warning scores here
use original threshold episodes, before operational confirmation.

| Missing sensors | Zero-fill Brier | Availability expert Brier | Brier reduction |
|---|---:|---:|---:|
| Wazuh | .00478319 | .00043982 | 90.8% |
| Suricata | .00030952 | .00021667 | 30.0% |
| AMiner | .00573892 | .00146248 | 74.5% |
| Suricata + Wazuh | .00464585 | .00082103 | 82.3% |
| AMiner + Wazuh | .00586381 | .00586843 | -0.08% |
| AMiner + Suricata | .00546038 | .00244195 | 55.3% |

Five of six tested degraded configurations improve probability error. Without
Wazuh, the matched expert recovers a timely warning that zero-filling misses.
Without AMiner, neither method gives a timely warning and the expert adds a
false episode. Suricata alone provides no improvement. Accuracy under changing
outages across fresh campaigns remains to be tested. See `sensor_outages.json`.

## Running-service latency and response measurement

A real local FastAPI process received 180 accelerated historical fox observations
through HTTP. All seven sensor configurations, total outage, recovery, and a
current-time live observation were exercised. Streaming and batch probabilities
matched exactly for all seven experts on 180 attack-period bins each.

| Local measurement | Result |
|---|---:|
| Median HTTP round trip | 59.71 ms |
| p95 HTTP round trip | 65.81 ms |
| Maximum HTTP round trip | 93.06 ms |
| p95 server handling | 63.74 ms |
| Test notifications acknowledged | 1/1 |
| Test acknowledgment delay | 24.59 ms |
| No-op handler completion delay | 30.69 ms |

This is local shadow-mode replay and a live-input smoke check. No production
sensor feed or defensive actuator was connected. Acknowledgment and no-op
completion are measured; **real attack prevention and response effectiveness are
not measured**. The receipt timing has just one sample. HTTP latency excludes
sensor collection and minute-bucket formation; warning confirmation adds a
separate one-minute delay for sustained threshold crossings. No earlier HTTP
latency baseline exists, so a latency percentage improvement is not claimed.
These values are from the verification rerun. The earlier run's p95 was 63.77 ms;
normal run-to-run variation is not a measured performance regression or gain.

The service records notification, acknowledgment, completion/failure and timing
in a local SQLite database, enabling a later instrumented deployment trial.
Live notifications also persist observation and receive timestamps plus the
finalized-bucket-to-notification age. That age excludes sensor collection and is
not populated for accelerated historical replay.
The timing table above is retained in `live_benchmark_pre_optimization.json`.
Current optimized measurements are in `live_benchmark.json`. See
[the runbook](../../docs/OPERATIONAL_IMPROVEMENTS.md).

The live-environment improvement remains **partially fulfilled**: local service
behavior and measurement infrastructure are verified; a real sensor deployment
and measured defensive response effectiveness are outstanding.

## Verification

All seven refitted experts reproduce the original frozen fox predictions exactly.
The streaming test exercises more than a complete trailing-feature window. New
regression checks cover spike suppression, bounded warning holds, cooldown,
outages, recovery, timestamp rejection, health/count separation, session isolation
and persistent, idempotent response receipts. Backend tests, the frontend build,
and desktop/mobile browser checks are recorded in `verification.json` and
`ui_verification.json`. Frontend lint exits successfully with existing warnings
in the earlier dashboard components.

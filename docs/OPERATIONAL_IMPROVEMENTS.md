# Streaming operational extension

The frozen research model remains the historical comparison. The new 30-minute
streaming extension is available at `/api/live`, and the dashboard overview shows
its paired warning-policy evaluation. Read the [current verified release](../experiments/operational_improvements/CURRENT_RELEASE.md).

## Prepare and run

Use the existing backend and research dependencies. The model builder needs the
prepared AIT datasets described in `data/README.md`. It refits the original fox
fold's six fitting campaigns, retains harrison for validation, and verifies
agreement with all seven frozen sensor experts. It does not fit on fox.

```powershell
python backend/research/evaluate_improvements.py
python backend/research/evaluate_selected_policy.py
python backend/research/prepare_live_model.py
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The local model and its checksum manifest are under `data/research/live/` and
excluded from Git. The loader accepts only this fixed locally built package.
The model contains Python/scikit-learn objects, so rebuilding is required after
incompatible environment changes. All seven experts remain in memory; each
stream's temporal histories are bounded to 60 minutes. Stream state is local to
one API process. Use one worker. Sessions expire after one hour of inactivity;
at most 32 sessions can be active. Restarting the server resets stream histories,
while notification and response records persist in `telemetry.sqlite3`.
The extension applies to `/api/live`. Frozen forecast probabilities are unchanged.
The earlier DARPA demonstration also received input, session, causal-replay and
illustrative-simulation corrections; its outputs are separate from the AIT study.
Healthy experts retain causal histories, while only the selected expert runs
the forecast estimators. This avoids redundant inference without dropping the
history needed when sensor availability changes.

## Feed observations

Create a stream by posting `{"mode":"live"}` to `/api/live/streams`. Store the
returned `stream_id`. Post one finalized minute bucket to
`/api/live/streams/{stream_id}/observations`:

```json
{
  "timestamp": 1794745800,
  "counts": {"aminer:detector_name": 3, "suricata:signature_name": 1},
  "heartbeats": {"aminer": 1794745800, "suricata": 1794745800}
}
```

The default `warning_profile` is `responsive`: one threshold crossing warns and
notifies immediately, with original episode timing. To request the earlier
quieter behavior explicitly, create with
`{"mode":"live","warning_profile":"confirmed"}`. That profile confirms two
buckets and has a five-minute notification cooldown; it may miss brief signals
or delay notifications. At 15 minutes its archived coverage decreases from 4/8
to 3/8. The responsive default preserves 4/8. Both profiles share the same
calibrated probabilities. Output includes the profile and raw `threshold_crossed`.
The validation-selected candidate remains a research result, not a live profile.

Use actual Unix timestamps from the collector. The example timestamp is only
illustrative: live buckets must have been finalized in the preceding 120 seconds;
one second of clock skew is tolerated. Future-dated buckets are otherwise rejected.
For historical or accelerated data, create a stream with `{"mode":"replay"}`.
The API accepts normalized detector counts; collecting and mapping the sensor's
raw logs into these one-minute buckets is the source application's responsibility.
Use the detector vocabulary from the model's preparation data; unseen detector
names enter that sensor's existing `OTHER` feature. Models should be validated
against the deployment's detector vocabulary before making performance claims.

Heartbeat timestamps must come from source health checks, not from the presence
of alerts. Include a healthy sensor even if it produced no alerts. Omitted
detector counts are zeros only for declared healthy sensors. Omitted or stale
heartbeats mark an outage, and counts from that sensor are ignored. Heartbeats
older than 90 seconds are stale. Future heartbeats are rejected. Timestamps must
increase on a one-minute grid; skipped buckets reset affected temporal histories.
Retrying the most recently committed timestamp with identical normalized evidence
returns the same result and notification ID. Changed evidence at that timestamp
returns 409; older timestamps return 422. This retry cache is process-local.
Inference or notification-storage failures return 503 after rolling state back;
retry that same bucket. There is no durable stream recovery across restarts.
Health declarations must reflect the collector's end-to-end data path. A process
heartbeat alone cannot establish bucket completeness; silent partial loss inside
a sensor declared healthy is not detected by this interface.

Output includes coherent probabilities at 1/2/5/10/15/30 minutes, the selected
sensor subset, available history, the 30-minute warning threshold, episode state,
`notify`, a notification ID when emitted, modeled response losses, and processing
latency. The API recommends actions but never executes a defense.
Live decisions include `decision_age_seconds` and `decision_window_end`. Action
delays begin at receipt time; expected loss uses linear CDF interpolation between
the saved horizons, an explicit modeling assumption. The target window still
ends 30 minutes after the observation, rather than 30 minutes after receipt.
Replay uses the original observation-time costs exactly.
`warning` and `episode_start` describe confirmed risk independently of outbound
`notify`. A cooldown can delay a notification, but cannot hide a confirmed warning.

## Record response outcomes

When a consumer handles an emitted notification, post to
`/api/live/notifications/{notification_id}/response`:

```json
{"status":"acknowledged","note":"Received by the local response consumer"}
```

Later post `completed` or `failed` with a note. These records use server arrival
time and preserve first acknowledgment/completion times across retries. Terminal
responses cannot be changed into another state. They provide receipt timing;
duplicate receipts preserve the original note, and failed receipts include
resolution latency. A backwards server clock is rejected instead of recording
negative receipt timing. Timing uses the local server clock and is not a signed
attestation of a consumer's actions.
they do not establish attack prevention. Measure actual mitigation using
separately verified endpoint outcomes and a suitable controlled deployment.
Close streams with `DELETE /api/live/streams/{stream_id}`.
Notification records also preserve observation and receive timestamps. Live
`bucket_to_notification_ms` measures the age of the finalized observation bucket
at notification creation, not raw sensor-to-detection latency. It is null during
historical replay and when tolerated clock skew prevents a meaningful age.

## Reproduce the measurements

With the API running at port 8000:

```powershell
python backend/research/benchmark_live.py --base-url http://127.0.0.1:8000
python backend/research/evaluate_sensor_outages.py
python backend/research/audit_operational_improvements.py
python backend/research/verify_selected_policy.py
python backend/research/verify_result_metrics.py
python backend/research/stress_refit_models.py --workers 4
python backend/research/stress_validate_runtime.py --workers 4
python backend/research/verify_frontend.py
python backend/research/verify_test_suite.py
python backend/research/verify_operational_ui.py
python backend/research/verify_operations_ui.py
python backend/research/write_release_report.py
```

The benchmark uses a persistent HTTP client, a single local service, 180 historical
observations, all sensor subsets and induced outages. Its consumer acknowledges
and completes a no-op test handler. Timing will vary by machine and load.
`GET /api/live/report` exposes the saved warning evaluation and benchmark;
`GET /api/live/status` shows local model readiness. Optional UI verification is
`python backend/research/verify_operational_ui.py`; it requires Playwright and
Chrome and temporarily starts the local API and Vite server on ports 8000/5173.
The operation check adds real playback/seek/simulation operations and intentionally
reorders HTTP responses to verify that newer controls keep their correct data.
The eight-fold stress refit takes several minutes and writes ignored trusted
local packages; it never replaces the frozen archives. Fault tests use temporary
databases. The benchmark writes shadow receipts to the local telemetry database.

## Local service boundary and evidence integrity

The API accepts actual loopback peers only, validates Host/browser Origin, limits
request bodies to 2 MiB and waits at most ten seconds for a complete body. Allowed
browser origins are localhost/127.0.0.1 at ports 5173, 8000 and 8001. A reverse
proxy must not expose this service to other clients. These checks are a local
research boundary, not user authentication or a production deployment design.
Opaque stream IDs and legacy HttpOnly session cookies isolate local temporal
state, but do not establish user identity. Limits deliberately reject excessive
work; the service is intended for one process and bounded local use.

Research reads verify frozen checksums or the independently verified metric-input
hashes before using cached content. Changed, unavailable or malformed evidence
returns 503. Keep `metrics_verification.json` with the dashboard artifacts; rerun
the metric audit after intentionally rebuilding score tables. Local manifests
detect drift but are not signatures against a hostile local writer. Model pickle
files must remain trusted local artifacts; never substitute downloaded packages.

The optional confirmed policy reduces the main 30-minute full-sensor alarm
burden, but its 15-minute diagnostic loses coverage. The default responsive
profile preserves original threshold behavior. Sensor probability comparisons use
one previously inspected research fold. Production latency, fresh-campaign
accuracy and measured defensive effectiveness require a connected deployment.

"""Create a self-contained, evidence-checked explanation of the MIS5 improvements.

Uses the existing Playwright/Chrome installation. No downloads, model training,
application changes, or fresh performance measurements are performed.
"""
from pathlib import Path
from datetime import datetime
from html import escape
import hashlib
import json
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
EVIDENCE = ROOT / 'experiments/operational_improvements'
PDF = OUT / 'MIS5_Improvements_Explained.pdf'
HTML = OUT / 'MIS5_Improvements_Explained.html'
FULL = 'aminer+suricata+wazuh'
sources = {}


def read(name):
    path = EVIDENCE / name
    content = path.read_bytes()
    sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(content).hexdigest()
    return json.loads(content)


def verify_hashes(mapping):
    for relative, expected in mapping.items():
        path = ROOT / relative.replace('\\', '/')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Evidence or source changed: {relative}')


def p(text, cls=''):
    return f'<p class="{cls}">{text}</p>'


def table(headers, rows, widths=None):
    cols = '' if not widths else '<colgroup>' + ''.join(f'<col style="width:{width}%">' for width in widths) + '</colgroup>'
    return '<table>' + cols + '<thead><tr>' + ''.join(f'<th>{value}</th>' for value in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{value}</td>' for value in row) + '</tr>' for row in rows) + '</tbody></table>'


def note(title, text, kind='note'):
    return f'<aside class="{kind}"><strong>{title}</strong><p>{text}</p></aside>'


def item(title, why, how, result, limit=None):
    body = f'<article class="improvement"><h3>{title}</h3><p><b>Why:</b> {why}</p><p><b>How:</b> {how}</p><p><b>Verified result:</b> {result}</p>'
    if limit:
        body += f'<p class="limit"><b>Boundary:</b> {limit}</p>'
    return body + '</article>'


pages = []


def page(title, subtitle, content, refs=''):
    pages.append((title, subtitle, content, refs))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    evaluation = read('evaluation.json')
    outages = read('sensor_outages.json')
    benchmark = read('live_benchmark.json')
    audit = read('audit.json')
    suite = read('test_suite_verification.json')
    stress = read('stress_validation.json')
    metrics = read('metrics_verification.json')
    frontend = read('frontend_verification.json')
    ui = read('ui_verification.json')
    operations_ui = read('operations_ui_verification.json')
    selection = read('selection_verification.json')
    verification = read('verification.json')
    release = read('release_decision.json')
    for evidence in (audit, suite, stress, metrics, frontend, ui, operations_ui, selection):
        if evidence['passed'] is not True:
            raise ValueError('A required verification artifact has not passed')
        verify_hashes(evidence.get('source_sha256', {}))
    verify_hashes(metrics['input_sha256'])
    verify_hashes(metrics['archive_sha256'])
    verify_hashes(release['source_sha256'])
    verify_hashes({f'experiments/operational_improvements/{name}': digest for name, digest in release['artifact_sha256'].items()})
    if release['default_warning_profile'] != 'responsive' or release['selector_promoted']:
        raise ValueError('Narrative must be reviewed for a changed release policy')
    if suite['tests'] != 95 or stress['experts'] != 56:
        raise ValueError('Narrative must be reviewed for changed verification scope')
    paired = benchmark['paired_inference_optimization']
    http = benchmark['http_round_trip']
    if not paired['predictions_identical'] or stress['maximum_archive_error'] != 0:
        raise ValueError('Forecast equivalence is not established')
    full_rows = {row['horizon']: row for row in evaluation['summary'] if row['available'] == FULL}
    thirty = full_rows[30]
    base, confirmed = thirty['baseline'], thirty['improved']
    false_reduction = 100 * (1 - confirmed['false_warning_episodes'] / base['false_warning_episodes'])
    notice_reduction = 100 * (1 - confirmed['notifications'] / base['notifications'])
    today = datetime.now().astimezone().strftime('%d %B %Y')

    page('MIS5 project improvements', 'What changed, why it was needed, how it works, and what the tests actually establish',
         '<div class="cover-label">IMPLEMENTATION &amp; VERIFICATION REPORT</div>'
         '<div class="hero">More reliable operation.<br>Clearer evidence.<br>Explicit tradeoffs.</div>'
         + p('This document explains the work completed for the requested future improvements: fewer unnecessary alarms, stronger operation with missing sensors, and measurement of warning latency and response handling.')
         + '<div class="stats"><div><strong>95</strong><span>backend tests passed</span></div><div><strong>56</strong><span>sensor experts checked</span></div><div><strong>2,007,012</strong><span>forecast values matched</span></div></div>'
         + table(['Area', 'Verified outcome'], [
             ['Alarm management', f'Optional confirmed profile: {false_reduction:.0f}% fewer false-warning episodes at 30 minutes. Responsive profile remains the default to preserve original timing.'],
             ['Sensor resilience', 'Automatic selection of the correct existing expert, outage handling, recovery, and abstention during total sensor loss.'],
             ['Performance', f'{paired["median_reduction_percent"]:.1f}% less median inference computation with identical probabilities; {http["p95_ms"]:.2f} ms final local HTTP p95.'],
             ['Reliability and truthful results', 'Retry/rollback fixes, input and local-service safeguards, independent metric reconstruction, causal replay, and corrected simulations.'],
         ], [25, 75])
         + note('Scope of this report', 'Evidence comes from recorded campaigns, controlled local fault tests, and a running local HTTP service. No external system was attacked. Production sensor deployment and actual mitigation effectiveness remain unmeasured.')
         + p(f'Prepared {today}. The PDF checks the retained evidence and source hashes; generating it does not rerun the experiments.', 'small'),
         'E1-E10. Full evidence index and reproduction instructions appear on pages 14-15.')

    page('Reading guide and original objectives', 'The report separates implementation changes, measured results, and remaining work.',
         note('Original future-improvement statement', '&ldquo;Reduce unnecessary alarms, strengthen performance when sensors are missing, and test the framework in a live environment to measure warning latency and response effectiveness.&rdquo;')
         + table(['Requested improvement', 'What was implemented', 'Status'], [
             ['Reduce unnecessary alarms', 'Explicit responsive/confirmed profiles, confirmation, bounded hysteresis, notification cooldown, and separate warning/notification metrics.', 'Implemented; benefit is conditional and optional.'],
             ['Handle missing sensors', 'Heartbeat-based routing to all seven availability experts, causal history management, gap/recovery resets and no-sensor abstention.', 'Runtime behavior verified; fresh-outage accuracy unmeasured.'],
             ['Measure live latency and effectiveness', 'Local HTTP service, latency timestamps, stored notification receipts, acknowledgment/completion/failure operations.', 'Partly fulfilled: real prevention and a production feed are outstanding.'],
         ], [23, 52, 25])
         + '<h2>Where to find the explanation</h2>'
         + '<div class="two-col"><div>'
         + p('<b>3.</b> Existing model and evaluation scope<br><b>4.</b> Fewer alarms and preserved responsiveness<br><b>5.</b> Missing sensors and recovery<br><b>6.</b> Inference speed and measured latency<br><b>7.</b> Live timing and response receipts<br><b>8.</b> Retry, rollback and database reliability')
         + '</div><div>'
         + p('<b>9.</b> Input, local-service and model safeguards<br><b>10.</b> Earlier-demo causal and session fixes<br><b>11.</b> Decision and simulation corrections<br><b>12.</b> Dashboard and evidence integrity<br><b>13.</b> Verification, rejected options and limits<br><b>14-15.</b> Evidence index and reproduction')
         + '</div></div>'
         + note('How each improvement is described', '<b>Why</b> identifies the limitation or defect. <b>How</b> explains the mechanism. <b>Verified result</b> states the observed outcome. <b>Boundary</b> prevents a local result from being mistaken for a universal guarantee.'),
         'E1, E2, E3, E10.')

    page('The model that remains unchanged', 'The main gains come from operating and validating the existing framework correctly.',
         p('The current AIT research model blends <b>75% counts-only risk</b> with <b>25% counts-and-state risk</b>, then applies the retained calibration. The state branch uses Bayesian evidence and forward Hidden Markov Model (HMM) state estimates. It forecasts the successful-root outcome at 1, 2, 5, 10, 15 and 30 minutes.')
         + '<div class="flow"><span>Detector counts<br>+ source health</span><i>&rarr;</i><span>Available-sensor<br>expert + history</span><i>&rarr;</i><span>Calibrated<br>risk</span><i>&rarr;</i><span>Warning policy<br>+ modeled action</span></div>'
         + item('Existing experts; new automatic routing', 'An offline expert can only handle an outage correctly if the runtime selects it and supplies the right history.', 'The service chooses among the seven nonempty subsets of AMiner, Suricata and Wazuh. Forecast weights, calibration and thresholds stay fixed.', 'All 56 fold-specific experts reproduce 2,007,012 retained forecast values with zero error. All 65 files checked inside the frozen package retain their original checksums.')
         + item('Keep fitting, validation and testing distinct', 'Fitting on the evaluated campaign or using its future outcomes during inference would make reported results misleading.', 'Each original fold uses six fitting campaigns, one validation campaign and one test campaign. Prefix tests compare predictions before later data is supplied; test truth/onset fields are removed or poisoned during inference checks.', 'The eight-fold conformance check passes: earlier predictions remain causal, test labels do not change inference, and probability vectors stay bounded and coherent across horizons.', 'These campaigns were inspected during development. The exercise is a reconstruction and functional audit, not a fresh independent performance study.')
         + '<h2>Terms used throughout</h2>'
         + table(['Term', 'Meaning here'], [
             ['Timely campaign coverage', 'A new warning or notification occurs inside the selected horizon before the recorded outcome. 5/8 campaigns is not classification accuracy.'],
             ['False-warning episode', 'A new warning starts earlier than the target horizon. It can occur during genuine earlier malicious activity; it is not automatically benign traffic.'],
             ['Brier score', 'Mean squared probability error; lower is better. Changing only the warning policy does not change it.'],
             ['Modeled response loss', 'Expected loss under configured damage, delay, effectiveness and disruption assumptions; not measured financial loss or attack prevention.'],
         ], [28, 72]),
         'E1, E4, E6, E9. Frozen model configuration: experiments/current_version/config.json.')

    alarm_rows = []
    for horizon in (30, 15):
        for key, name in (('baseline', 'Responsive (default)'), ('improved', 'Confirmed (optional)')):
            value = full_rows[horizon][key]
            alarm_rows.append([f'{horizon} min', name, f'{value["timely_notification"]}/8', str(value['false_warning_episodes']), str(value['notifications']), f'{value["mean_notification_lead_minutes"]:.2f} min'])
    page('Fewer unnecessary alarms', 'The quieter policy is available explicitly; original responsiveness is the default.',
         item('Confirmation and bounded episode handling', 'Brief threshold crossings and repeated notifications can increase operator burden. Suppression, however, can also remove useful short signals.', 'The confirmed profile requires two consecutive above-threshold minute buckets. It uses two below-clear-threshold buckets, a clear ratio of 0.8, a 120-second maximum hold below the warning threshold, and a 300-second notification cooldown. Context changes and long gaps reset episode state.', f'At 30 minutes with all sensors, false episodes fall from {base["false_warning_episodes"]} to {confirmed["false_warning_episodes"]} ({false_reduction:.0f}% fewer); notifications fall from {base["notifications"]} to {confirmed["notifications"]} ({notice_reduction:.1f}% fewer). The same five campaigns receive timely notifications.')
         + table(['Horizon', 'Profile', 'Timely', 'False episodes', 'Notices', 'Mean lead'], alarm_rows, [11, 28, 10, 16, 12, 23])
         + item('Separate warning visibility from notification traffic', 'A cooldown bug could hide a confirmed warning until another outbound notification was permitted.', 'Warning state, episode starts and notification emission are tracked independently. Cooldown limits outbound traffic while the confirmed episode remains visible. A pending notification can be emitted if high risk persists until cooldown expires.', 'An independent policy oracle reproduces all 112 campaign/sensor/horizon cases and 14 aggregates. Both episode and notification metrics are retained.')
         + note('Why the quieter profile is not the default', 'First timely notification is later in four of the five warned campaigns; fox loses 10 minutes of lead. At 15 minutes, coverage falls from 4/8 to 3/8. The higher aggregate mean lead does not mean every warning became earlier. The responsive default exactly preserves original warning/notification traces in all 112 fixed-availability cases.', 'caution')
         + p(f'Both profiles use the same forecast probabilities. The full-sensor 30-minute mean Brier remains {thirty["mean_brier_unchanged"]:.9f}. No probability-accuracy gain is attributed to alarm suppression.', 'small'),
         'E1, E2, E3, E9. Implementation: warning_policy.py and warning_profiles.py.')

    outage_rows = [[', '.join(row['missing']), f'{row["zero_fill"]["brier"]:.8f}', f'{row["availability_expert"]["brier"]:.8f}', f'{row["brier_reduction_percent"]:.2f}%'] for row in outages['rows']]
    page('Stronger operation with missing sensors', 'An unavailable sensor is different from a healthy sensor reporting zero alerts.',
         item('Source-health routing and honest abstention', 'Zero-filling a missing source can falsely present an outage as evidence of quiet traffic. A stale sensor can also contaminate trailing features.', 'Heartbeats describe source health independently of alert counts. A missing heartbeat or one older than 90 seconds marks a sensor unavailable. Its counts are ignored; the matching existing expert is selected. If no sensors remain, risk and action are withheld.', 'All seven nonempty sensor subsets, total outage, stale/missing heartbeats and recovery pass controlled operation checks. Deliberately poisoned unavailable-sensor counts do not change forecasts.', 'Health must represent the complete collection path. A sensor claiming to be healthy can still suffer silent partial loss that this interface cannot infer.')
         + item('Preserve usable history; reset broken history', 'Fallback needs valid past observations. Reusing stale history after an outage or gap can create an incorrect temporal state.', 'All experts whose required sensors are healthy continue to advance. On gaps or re-entry after an outage, affected histories restart. Each stream retains at most 60 minutes of feature history.', 'Stream results match independently rebuilt batch prefixes, including transitions and skipped buckets. Cold recovery is explicit rather than silently filled with invented observations.')
         + '<h2>Measured outage comparison on the fox fold</h2>'
         + table(['Missing sensor(s)', 'Naive zero-fill Brier', 'Matching expert Brier', 'Error reduction'], outage_rows, [30, 25, 25, 20])
         + note('What these numbers do and do not show', 'Five of six whole-campaign outage settings improve Brier error against a naive full-sensor zero-fill comparator. Suricata alone is slightly worse (about 0.08%). Without Wazuh, the expert recovers a timely warning missed by zero-fill; without AMiner, neither warns in time and the expert adds a false episode. These are existing experts on one inspected fold, not new learned weights or fresh dynamic-outage accuracy evidence.', 'caution'),
         'E3, E4, E5. Implementation: live_router.py and streaming_forecast.py.')

    page('Less redundant inference computation', 'Maintain the histories needed for fallback, then forecast only with the selected expert.',
         item('Avoid seven redundant forecasts per observation', 'The eager implementation evaluated forecast estimators for every healthy sensor expert, although the response uses only the selected expert.', 'State/history updates are separated from forecast prediction. Healthy experts keep their causal histories; only the chosen expert evaluates its forecasting estimators and calibrators.', f'A paired comparison on {paired["previous_eager"]["samples"]} archived buckets reduces median inference computation by {paired["median_reduction_percent"]:.1f}%, with exactly identical selected probabilities.')
         + table(['Inference measurement', 'Previous eager reference', 'Selected expert'], [
             ['Median', f'{paired["previous_eager"]["median_ms"]:.2f} ms', f'{paired["current_selected_only"]["median_ms"]:.2f} ms'],
             ['p95', f'{paired["previous_eager"]["p95_ms"]:.2f} ms', f'{paired["current_selected_only"]["p95_ms"]:.2f} ms'],
         ], [38, 31, 31])
         + '<h2>Final running-service measurement</h2>'
         + table(['Local HTTP measurement', 'Observed value'], [
             ['Archived observations', str(benchmark['observations'])],
             ['Median round trip', f'{http["median_ms"]:.2f} ms'],
             ['p95 round trip', f'{http["p95_ms"]:.2f} ms'],
             ['Maximum round trip', f'{http["max_ms"]:.2f} ms'],
             ['p95 server processing', f'{benchmark["server_processing"]["p95_ms"]:.2f} ms'],
             ['Acknowledged / emitted test notifications', f'{benchmark["receipts_acknowledged"]} / {benchmark["notifications"]}'],
             ['No-op handler completions', str(benchmark['noop_handlers_completed'])],
         ], [68, 32])
         + note('Two different measurements', 'The 82.9% result is a same-process paired inference comparison. HTTP latency includes the complete tested request path, validation, transactional checkpoints and occasional receipt persistence. Its speedup is not derived by comparing separate historical HTTP runs. The final p95 is 38.19 ms; the older 27.27 ms run is not the current result.', 'caution')
         + p('p95 is the empirical 95th percentile of this 180-observation local run. The observed 375.88 ms maximum is retained. Neither statistic is a production guarantee or a measurement of sensor collection, raw-event detection latency, or minute-bucket formation.'),
         'E7. Benchmark: backend/research/benchmark_live.py; retained timing data: live_benchmark.json.')

    page('Live timing and response measurement', 'A running local service was exercised; deployment effectiveness is still outstanding.',
         item('Introduce a streaming shadow-mode API', 'Offline scores alone do not show whether observations can be processed through an actual service, or whether its behavior remains correct during outages.', 'The /api/live service accepts normalized finalized one-minute count buckets and source heartbeats. Replay mode permits archived timestamps; live mode requires buckets finalized within the previous 120 seconds, with one second of clock tolerance.', 'A real local HTTP process handled 180 accelerated fox observations, all sensor subsets, total outage, recovery and a current-time live smoke observation. Probabilities and modeled actions were compared with batch results.', 'No production AMiner, Suricata or Wazuh feed was connected. Collector adapters and end-to-end deployment behavior were not measured.')
         + item('Make warning and response timing auditable', 'Without observation, receipt and notification timestamps, server speed can be mistaken for end-to-end warning latency.', 'Notification payloads retain observation time, server receipt time, stream mode, warning profile and decision age. Live bucket-to-notification age is recorded when meaningful; historical replay is not assigned a misleading wall-clock age.', 'The storage and timing paths are exercised by API tests and the HTTP benchmark. The API exposes /status for model readiness and /report for saved results.')
         + item('Persist response outcomes without claiming prevention', 'An acknowledgment or completed handler does not establish that a threat was stopped, but these operations must be measurable before a real trial.', 'SQLite stores emitted, acknowledged, completed or failed receipt state. Consumers post response receipts; server arrival timestamps produce acknowledgment, completion and resolution timing.', f'The final benchmark records {benchmark["receipts_acknowledged"]}/{benchmark["notifications"]} acknowledgments and {benchmark["noop_handlers_completed"]} no-op completions. Median acknowledgment is {benchmark["acknowledgment"]["median_ms"]:.2f} ms and median no-op completion is {benchmark["noop_completion"]["median_ms"]:.2f} ms after emission.', 'Only five test notification samples are present in this final run. No defensive actuator was connected and no causal reduction in attack success was measured.')
         + note('Status of the original live-environment objective', '<b>Partially fulfilled.</b> Service behavior, local handling latency and response-recording infrastructure are implemented. Real deployment latency and response effectiveness still require a controlled trial with actual source feeds and verified endpoint outcomes.', 'caution'),
         'E1, E3, E7. API/runbook: backend/app/routers/live_router.py; docs/OPERATIONAL_IMPROVEMENTS.md.')

    page('Reliable retries, failures and persistence', 'These fixes address concrete operational defects rather than improving forecast accuracy.',
         item('1. Idempotent observation retries', 'A lost HTTP reply can make a caller retry an already processed bucket, advancing history twice or creating duplicate notifications.', 'The most recently committed normalized observation has a canonical fingerprint and cached response. An identical retry returns the same result and notification ID. Different evidence at that timestamp returns 409; older buckets are rejected.', f'The stress flows check {stress["exact_retries_checked"]} exact retries and {stress["conflicts_rejected"]} conflicts. Concurrent identical-retry tests verify one commit.', 'The cache is process-local and covers only the latest observation; it is not durable restart recovery.')
         + item('2. Atomic state rollback after failure', 'Forecast or database failure could leave temporal state advanced even though the caller received an error.', 'Before mutation, the service checkpoints expert histories and warning state. Inference or notification-storage exceptions restore both and return 503 so the same bucket can be retried.', f'{stress["persistence_faults_recovered"]} real-model persistence faults recover in stress testing; additional tests inject inference failures and verify unchanged state before retry.')
         + item('3. Immutable receipt timing and outcomes', 'Repeated or contradictory receipts could overwrite the first timing or note, or change a completed/failed result.', 'Duplicate receipts preserve the first acknowledgment and note. Terminal states reject incompatible changes. Failed outcomes now record resolution time; backward-clock receipts are rejected instead of recording negative latency.', 'Tests cover duplicate acknowledgment and terminal receipts, incompatible transitions, failed resolution timing and a backward clock.')
         + item('4. Close database connections on all paths', 'An unclosed connection is a resource leak that can accumulate over repeated operations or failed transactions.', 'Database context managers commit or roll back transactions and close connections in a finally block, including exception paths.', 'Backend checks cover database lifecycle behavior alongside persistence faults. This fixes a connection-resource leak; it is not evidence that a data-exfiltration incident occurred.'),
         'E4, E6. Implementation: live_router.py, streaming_forecast.py, ingestion/database.py.')

    page('Input and local-service safeguards', 'Reject malformed or excessive work before it can corrupt state or mislead callers.',
         item('5. Validate normalized evidence and work limits', 'Non-finite values, overflowing count totals, invalid timestamps and unbounded generation requests can crash processing, poison histories or waste resources.', 'Typed schemas reject extra fields, invalid sensor/detector names, nonnumeric/negative/non-finite counts and overflowing totals. Counts are capped at 4,096 entries. Live timestamps and minute-grid checks agree with the stream model. Legacy batches are bounded to 500 events; synthetic generation to 5,000 steps with rates in [0,1].', 'Malformed, forged-label/action, NaN/Infinity, extreme-count, time-grid and work-bound tests verify rejection without advancing temporal state.')
         + item('6. Protect SQL identifiers and synthetic run boundaries', 'Parameterized values do not protect an interpolated table name. A blank run ID could also make synthetic replacement affect other runs.', 'Table identifiers are allowlisted. Synthetic writes require a nonblank run ID of at most 128 characters. Run values remain bound SQL data; event dictionaries are copied rather than modified. Empty generation removes only its own previous run.', 'Tests reject untrusted identifiers, verify quoted IDs remain data, preserve other runs, and confirm caller input dictionaries are unchanged.')
         + item('7. Restrict the local HTTP boundary', 'Cross-site browser requests or remote peers should not be able to mutate this unauthenticated research service.', 'The API checks the actual loopback peer, trusted Host and declared local browser origins; spoofed forwarded headers do not establish trust. Duplicate Origin/length headers and ambiguous length encodings are rejected. Bodies are capped at 2 MiB, including chunked requests, with a ten-second receive timeout.', 'Tests exercise remote peers, spoofed headers, forbidden origins, cross-site fetches, oversized/chunked/slow bodies and declared-length mismatches.', 'This is a local boundary, not production authentication. Any proxy exposing it externally would need a separate deployment design.')
         + item('8. Fail safely on invalid model packages and errors', 'A file can deserialize while still missing experts, having invalid probability matrices or mismatched feature dimensions. Default errors can also echo rejected input.', 'A checksum is checked before loading the fixed trusted-local pickle. Structural validation checks all seven experts, fitting metadata, dimensions, probability normalization, calibrators and horizons. Validation responses omit rejected input values.', 'Missing, corrupt, unloadable and structurally partial packages cannot report ready; non-finite/secret-like rejected inputs are exercised without reflecting their values.', 'Pickle remains trusted local code. Checksums are not signatures, and a hostile local writer remains outside this protection.'),
         'E4, E6. Implementation: request_safety.py, main.py, legacy_schemas.py, package_validation.py.')

    page('Earlier-demo correctness and isolation', 'These changes apply to the DARPA/synthetic demonstration, separately from AIT forecast scores.',
         item('9. Independent causal historical replay', 'Seeking to an earlier alert through a shared stateful inference service could reuse later belief state or reset another caller.', 'Each historical batch owns a fresh temporal pipeline while reusing fitted read-only models. The dashboard caches each causal per-event result and seeks locally. Earlier timestamps on an individual stream are rejected unless that caller resets it.', 'Batch prefixes match separate shorter runs. Browser tests step forward and seek/reset backward without calling the state-mutating /pipeline/infer route; past recommendations stay identical.')
         + item('10. Separate individual clients', 'One shared individual-inference history allows one client or reset operation to affect another client.', 'Opaque HttpOnly, SameSite=Strict cookies identify per-client temporal contexts under /api/pipeline. Contexts expire after an hour of inactivity, with a 32-context cap. Each reset affects only its own context.', 'Two-client tests verify independent histories and reset behavior.', 'Cookies isolate anonymous local state; they are not authenticated user identities. Contexts are process-local.')
         + item('11. Bounded history and truthful provenance', 'Unbounded legacy history wastes memory. Recording a posterior as the prior misstates how a recommendation was reached.', 'The legacy observation history is capped at 15 and event history at 30. The previous dominant state is captured before filter update and recorded as the prior. A B0 rule-expression precedence issue is corrected so a flood signature works even when a port is empty or nonnumeric.', 'Tests exercise 100 sequential events, validate history bounds and prior traces, and confirm flood-signature behavior across port representations.')
         + item('12. Serialize mutable evaluation runners', 'Concurrent legacy evaluation runs can interleave mutable shared runner state and mix results.', 'A reentrant lock serializes endpoints that operate on the shared legacy evaluation runner. Independent current-model streams and historical batches retain their own state.', 'A concurrency check verifies the guarded legacy runner does not interleave.', 'Serialization can reduce throughput for simultaneous legacy evaluation requests. It is a correctness choice, not a performance gain.'),
         'E6, E8. Implementation: pipeline.py, pipeline_router.py, evaluation/serialization.py, LegacyDashboard.tsx.')

    page('Trustworthy decisions and simulations', 'Optimal means best under the specified mathematical assumptions, not guaranteed real-world success.',
         item('13. Use unrounded expected utilities to choose actions', 'Rounding utilities before ranking can create an artificial tie and select the wrong action.', 'The legacy Decision Network validates the supplied probability distribution and chooses the maximum using full-precision utility values. Formatting is kept separate from selection; unknown actions and invalid baselines are rejected.', 'A deliberately close-utility example and 200 seeded probability distributions confirm selection agrees with direct expected-utility maximization.')
         + item('14. Remove invented differences between identical actions', 'Different trajectory rules for the baseline and hypothetical series could show a benefit even when both selected actions were identical.', 'Both series now use the same explicitly illustrative cumulative-loss rule. Equal action and belief inputs therefore produce equal trajectories and zero difference. Both bar series use one actual scale, including zero-height bars, and the UI uses model units instead of money/prevention claims.', 'Tests compare every action with itself. Real-browser checks confirm identical Monitor losses and equal bar heights, and reject stale simulation replies.', 'Trajectory progression and effectiveness are assumptions. Existing cached legacy RQ reports may predate this correction and are labeled separately.')
         + item('15. Account for forecast age in live action costs', 'Applying a fresh-observation action formula to an older bucket can overestimate the time left for an intervention.', 'Live costs use receipt-time age plus action delay, while keeping the endpoint at observation time + 30 minutes. Onset probability between saved horizons is linearly interpolated. Replay keeps the original observation-time formula exactly.', 'Two hundred seeded coherent risk vectors are checked against an independent interpolation/loss calculation. Modeled action costs do not optimistically improve simply because the forecast gets older.', 'Interpolation is a decision-model assumption, not a newly calibrated horizon or a new forecast for 30 minutes after receipt.')
         + note('The current response-cost rule', '<span class="formula">disruption + 20 &times; [p30 &minus; 0.8 &times; effect &times; max(0, p30 &minus; CDF(age + action delay))]</span><br>For replay, age = 0. The service selects the lowest-cost action among Monitor, Restrict, Block and Isolate. These checks verify arithmetic under configured costs; they do not verify assumed effectiveness in a real incident.'),
         'E4, E6, E7, E8. Implementation: decision_network.py, onset_decision.py, WhatIfSimulator.tsx.')

    page('Dashboard and evidence integrity', 'A correct model is not sufficient if the interface pairs it with stale data or unverified results.',
         item('16. Prevent old HTTP replies from replacing new choices', 'Rapid changes of horizon, campaign, scenario, mode or action can cause a slower old response to arrive last and display results for the wrong controls.', 'Responses and failures are keyed to their inputs. Requests are aborted or their stale results ignored on changes. Playback resets appropriately, loading states show no invented beliefs, and what-if action selection is preserved. Errors clear on successful retrieval.', 'Real-browser tests intentionally reorder horizon, legacy-mode and simulation replies; the newest controls retain the correct results. Play/pause/step/reset/jump/campaign-change operations pass without browser errors or API server failures.')
         + item('17. Verify evidence before serving cached content', 'Caching by filename alone can continue showing an old verified result after the file is changed or corrupted.', 'Research JSON/NPZ reads verify the frozen manifest or independently audited metric-input hash before content-keyed decoding. Plot downloads use their export manifest. Missing, changed, malformed or unverified evidence returns 503. The exact verified bytes are served for downloads.', 'Isolated tamper tests prime the cache, change evidence, confirm rejection, restore evidence and confirm recovery. Original archives are never corrupted for this test.', 'Local manifests detect drift; they are not signatures against an attacker who can replace both data and manifests.')
         + item('18. Independently reconstruct the reported numbers', 'Copying dashboard constants or calling the same scoring implementation twice would not independently establish that the reported metrics were computed correctly.', 'The audit recalculates Brier, rank/tie-aware average precision, strict warning episodes, lead, burden and aggregates from prediction archives. It reconstructs the original constrained threshold search, snapshots input hashes and rejects changes during a run.', f'{metrics["total_score_rows"]:,} score rows, {metrics["aggregate_rows"]:,} aggregate rows, {metrics["prediction_archives_checked"]} archives and {metrics["validation_thresholds_checked"]:,} validation threshold selections pass.', 'Threshold optimality is limited to the original candidate grid, budget and objective. This does not establish a globally optimal architecture.')
         + p('Labels now distinguish archived replay from live service behavior, replace &ldquo;Reset to Live&rdquo; with &ldquo;Reset to Observed Belief&rdquo;, identify illustrative effects and model units, and remove an unqualified &ldquo;optimal balance&rdquo; claim. Production build and lint pass without frontend warnings.', 'small'),
         'E6, E8, E9. Implementation: artifact_store.py, research_router.py, App.tsx and related components.')

    regressions = [[row['campaign'], row['available'].replace('+', ' + '), str(row['horizon']) + ' min'] for row in selection['test_regressions']]
    page('Verification, tradeoffs and remaining work', 'The strongest supported version preserves useful behavior and keeps its limits visible.',
         table(['Check', 'Retained result'], [
             ['Backend suite', f'{suite["tests"]} passed; no failures, errors or skips.'],
             ['Eight-campaign model conformance', f'{stress["experts"]} experts; {stress["forecast_values_checked"]:,} values; archive and stream maximum error 0.'],
             ['Controlled API operations', f'{stress["operation_observations"]:,} observations; {stress["exact_retries_checked"]} exact retries; {stress["conflicts_rejected"]} conflicts; {stress["persistence_faults_recovered"]} recovered persistence faults.'],
             ['Metrics and thresholds', f'{metrics["total_score_rows"]:,} score rows; {metrics["aggregate_rows"]:,} aggregates; {metrics["validation_thresholds_checked"]:,} original-grid optima.'],
             ['Frontend and browser', 'Build/lint; desktop/mobile research view; real controls and deliberately reordered responses pass.'],
             ['Frozen evidence', f'{verification["frozen_files_unchanged"]} frozen-package files retain original checksums.'],
         ], [36, 64])
         + '<h2>Why the validation-selected candidate was not released</h2>'
         + p('Eleven warning candidates were evaluated in 112 fold/sensor/horizon settings using outer-validation forecasts and fixed thresholds. Selection required no validation loss in coverage or first lead, and no increase in false notifications, false episodes, negative warning minutes or total notifications. The selected policy still regressed in four subsequent evaluation settings:')
         + table(['Campaign', 'Sensor subset', 'Horizon'], regressions, [23, 57, 20])
         + p('It remains research-only. The release uses the responsive default and does not switch behavior based on campaign identity. Reusing these inspected validation campaigns is not an independent confirmation.')
         + note('Consequences that remain explicit', 'Quieter alarms can lose lead or miss brief signals. Total sensor loss requires abstention. Input bounds reject excessive work. Transactional and validation safeguards have runtime costs. Streams reset on restart, and multi-worker/durable stream recovery is not implemented. Default 30-minute coverage remains 5/8, not perfect coverage.', 'caution')
         + p('<b>Outstanding:</b> fresh independent campaigns; complete source-feed adapters; dynamic-outage accuracy after cold recovery; production-load and security assessment; authenticated durable deployment; and a controlled actuator trial with verified attack outcomes. A narrow source scan found no matching key/private-key patterns, but excluded data/private folders and was not an exhaustive credential or dependency audit. Existing Python environment warnings were observed; frontend lint is clean.', 'small'),
         'E1, E4, E6, E8, E9, E10. No actual mitigation effectiveness or universal optimality claim is made.')

    reference_rows = [
        ['E1', 'Current behavior and combined verification', 'CURRENT_RELEASE.md; verification.json; release_decision.json'],
        ['E2', 'Per-campaign and aggregate warning-policy comparison', 'evaluation.json'],
        ['E3', 'Independent warning-policy oracle and outage checks', 'audit.json; audit_operational_improvements.py'],
        ['E4', 'All-fold real-model conformance and operation tests', 'stress_validation.json; stress_model_fitting.json; stress_validate_runtime.py'],
        ['E5', 'Single-fold availability experts versus naive zero-fill', 'sensor_outages.json'],
        ['E6', 'Observed backend test results and checked source hashes', 'test_suite_verification.json; data/ui-checks/hardening-tests.log'],
        ['E7', 'Current paired inference and running-service timings', 'live_benchmark.json; benchmark_live.py'],
        ['E8', 'Observed frontend and browser verification', 'frontend_verification.json; ui_verification.json; operations_ui_verification.json'],
        ['E9', 'Independent score/aggregate/threshold arithmetic', 'metrics_verification.json; verify_result_metrics.py'],
        ['E10', 'Candidate selection and why it was not promoted', 'selection_verification.json; policy_selection.json; selected_evaluation.json; SELECTION_PROTOCOL.md'],
    ]
    page('Evidence index and implementation map', 'References are local project artifacts, so the report remains usable without internet access.',
         p('Unless another location is shown, result files below are under <code>experiments/operational_improvements/</code>. Research scripts are under <code>backend/research/</code>. The companion <code>MIS5_Improvements_Explained.validation.json</code> records the full SHA-256 digests of report inputs and the generated PDF.')
         + table(['Ref.', 'Evidence purpose', 'Files'], reference_rows, [8, 37, 55])
         + '<h2>Where the implementation lives</h2>'
         + table(['Improvement family', 'Primary project files'], [
             ['Warnings and streaming', 'backend/app/models/warning_policy.py; warning_profiles.py<br>backend/research/streaming_forecast.py'],
             ['Live operations and local boundary', 'backend/app/routers/live_router.py<br>backend/app/request_safety.py; main.py'],
             ['Packages and decision costs', 'backend/app/models/package_validation.py; onset_decision.py; decision_network.py'],
             ['Database and earlier demo', 'backend/app/ingestion/database.py<br>backend/app/models/pipeline.py<br>backend/app/routers/pipeline_router.py; legacy_schemas.py'],
             ['Dashboard and evidence', 'backend/app/artifact_store.py; routers/research_router.py<br>frontend/src/App.tsx; LegacyDashboard.tsx; OperationalResults.tsx; components/'],
         ], [33, 67])
         + p('Historical REPORT.md and AUDIT.md retain earlier study stages and timing/test counts. They should not replace the current evidence cited here. The PDF uses the latest verified release numbers and explicitly retains negative or inconclusive results.', 'small'),
         'E1-E10. Full digests are stored in the companion validation JSON, not presented as security signatures.')

    page('How to reproduce and use the report', 'Reproduction is optional; the PDF documents completed work and retained observations.',
         '<h2>1. Check the saved evidence and rebuild this PDF</h2>'
         + '<pre>python reports/build_improvements_pdf.py</pre>'
         + p('The PDF builder validates the current source/evidence digests before composing the document. It checks every printed page for overflow and overlap with its footer, then confirms the PDF page count and required result text. It never changes frozen forecasts or application code.')
         + '<h2>2. Reproduce functional and arithmetic checks</h2>'
         + '<pre>python backend/research/verify_result_metrics.py\npython backend/research/stress_refit_models.py --workers 4\npython backend/research/stress_validate_runtime.py --workers 4\npython backend/research/audit_operational_improvements.py\npython backend/research/verify_selected_policy.py\npython backend/research/verify_test_suite.py\npython backend/research/verify_frontend.py\npython backend/research/verify_operational_ui.py\npython backend/research/verify_operations_ui.py</pre>'
         + p('Prepared local datasets and the existing dependencies are required. The eight-fold refit can take several minutes and writes ignored trusted-local packages. Fault tests use temporary databases. Browser checks require local Chrome/Playwright and free ports 8000/5173. They stop only the processes they start.')
         + '<h2>3. Reproduce running-service timing</h2>'
         + '<pre>python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001\n\n# In a second terminal:\npython backend/research/benchmark_live.py --base-url http://127.0.0.1:8001</pre>'
         + p('Enter each command as a single line in PowerShell. The local model must be prepared as described in docs/OPERATIONAL_IMPROVEMENTS.md. The benchmark writes shadow response receipts, not real defensive actions. Timing varies by machine and load.')
         + '<h2>4. Refresh the release after intentionally regenerating evidence</h2>'
         + '<pre>python backend/research/write_release_report.py\npython reports/build_improvements_pdf.py</pre>'
         + note('Safe interpretation for a presentation or project submission', 'The project now provides configurable alarm management, automatic sensor-availability handling, faster equivalent inference, safer local operation, and independently audited results. The measured benefits apply to the stated archived/local tests. Production effectiveness and flawless behavior have not been demonstrated.'),
         'Setup and API details: docs/OPERATIONAL_IMPROVEMENTS.md; data/README.md; README.md.')

    css = '''
    @page { size: A4; margin: 0; }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body { color:#223347; font-family: "Segoe UI", Arial, sans-serif; font-size:12.2px; line-height:1.48; background:#dce3e9; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .sheet { width:210mm; height:297mm; padding:15mm 16mm 19mm; position:relative; background:white; break-after:page; margin:0 auto 12px; }
    .sheet:last-child { break-after:auto; }
    .topline { display:flex; justify-content:space-between; border-top:4px solid #087e8b; padding-top:10px; margin-bottom:23px; color:#61748a; font-size:9px; letter-spacing:1.5px; font-weight:700; }
    h1 { font-size:29px; line-height:1.15; color:#102a43; margin:0 0 9px; letter-spacing:-.6px; }
    .subtitle { color:#607489; font-size:13.5px; line-height:1.45; margin:0 0 23px; }
    h2 { margin:19px 0 8px; font-size:16px; line-height:1.25; color:#123c56; }
    h3 { color:#08717d; font-size:14px; line-height:1.3; margin:0 0 5px; }
    p { margin:0 0 10px; }
    .improvement { margin:0 0 17px; padding-bottom:10px; border-bottom:1px solid #e3eaf0; break-inside:avoid; }
    .improvement p { margin:0 0 5px; }
    b, strong { color:#102a43; }
    .limit, .small { color:#53677d; font-size:11px; line-height:1.45; }
    table { width:100%; border-collapse:collapse; margin:13px 0 17px; table-layout:fixed; font-size:11.3px; line-height:1.4; }
    th { text-align:left; background:#103e55; color:#fff; font-weight:600; padding:9px 10px; vertical-align:top; }
    td { padding:8px 10px; border-bottom:1px solid #dbe5ed; vertical-align:top; overflow-wrap:anywhere; }
    tr:nth-child(even) td { background:#f1f6f9; }
    aside { padding:12px 14px; background:#eaf5f5; border-left:4px solid #087e8b; margin:14px 0; break-inside:avoid; font-size:11.8px; line-height:1.46; }
    aside p { margin:4px 0 0; }
    .caution { background:#fff6e7; border-left-color:#b77a17; }
    .two-col { display:grid; grid-template-columns:1fr 1fr; gap:23px; }
    .two-col p { line-height:2; }
    .cover-label { font-size:10px; color:#087e8b; font-weight:700; letter-spacing:2px; margin:26px 0 12px; }
    .hero { color:#102a43; font-size:34px; line-height:1.15; font-weight:700; letter-spacing:-.6px; margin-bottom:23px; }
    .stats { display:grid; grid-template-columns:1fr 1fr 1.35fr; gap:9px; margin:22px 0; }
    .stats div { background:#103e55; padding:16px 12px; color:white; border-radius:5px; }
    .stats strong { display:block; color:white; font-size:28px; line-height:1.15; }
    .stats span { display:block; color:#c6e6eb; font-size:10px; padding-top:6px; }
    .flow { display:flex; align-items:center; gap:8px; margin:20px 0; font-size:11px; text-align:center; }
    .flow span { flex:1; background:#eaf5f5; border:1px solid #bddcde; border-radius:4px; padding:13px 5px; }
    .flow i { font-size:20px; color:#087e8b; font-style:normal; }
    pre { white-space:pre-wrap; overflow-wrap:anywhere; font-family:Consolas,monospace; color:#24465d; background:#f0f5f8; padding:12px 14px; font-size:10.8px; line-height:1.5; border:1px solid #dbe5ed; border-radius:4px; margin:9px 0 12px; }
    code { font-family:Consolas,monospace; font-size:10.5px; overflow-wrap:anywhere; }
    .formula { font-size:12px; color:#103e55; display:block; margin-bottom:7px; }
    footer { position:absolute; left:16mm; right:16mm; bottom:9mm; border-top:1px solid #ccdbe4; padding-top:7px; font-size:8px; color:#61748a; display:flex; justify-content:space-between; gap:16px; }
    .refs { max-width:85%; line-height:1.4; }
    #page-14 table { font-size:10.4px; line-height:1.35; }
    #page-14 td { padding:6px 8px; }
    #page-15 pre { line-height:1.4; padding:10px 12px; margin:8px 0 10px; }
    @media print { body { background:white; } .sheet { margin:0; } }
    '''
    sheets = []
    for number, (title, subtitle, content, refs) in enumerate(pages, 1):
        sheets.append(f'<section class="sheet" id="page-{number}"><div class="page-content"><div class="topline"><span>MIS5 / PROJECT IMPROVEMENTS</span><span>EVIDENCE-CHECKED REPORT</span></div><h1>{title}</h1><p class="subtitle">{subtitle}</p>{content}</div><footer><span class="refs">{refs}</span><span>{number} / {len(pages)}</span></footer></section>')
    document = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>MIS5 - Improvements Explained and Verified</title><style>' + css + '</style></head><body>' + ''.join(sheets) + '</body></html>'
    HTML.write_text(document, encoding='utf-8')
    previews = OUT / 'previews'
    previews.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        browser_page = browser.new_page(viewport=dict(width=900, height=1300), device_scale_factor=1)
        browser_page.goto(HTML.as_uri(), wait_until='networkidle')
        browser_page.emulate_media(media='print')
        layout = browser_page.locator('.sheet').evaluate_all('''elements => elements.map((element, index) => {
          const body=element.querySelector('.page-content').getBoundingClientRect();
          const footer=element.querySelector('footer').getBoundingClientRect();
          return {page:index+1,clearance_px:footer.top-body.bottom,
                  horizontal_overflow:element.scrollWidth>element.clientWidth+1,
                  vertical_overflow:element.scrollHeight>element.clientHeight+1};
        })''')
        bad = [row for row in layout if row['clearance_px'] < 9 or row['horizontal_overflow'] or row['vertical_overflow']]
        if bad:
            browser.close()
            raise ValueError(f'Page content needs layout adjustment: {bad}')
        browser_page.pdf(path=str(PDF), prefer_css_page_size=True, print_background=True, tagged=True, outline=True)
        text_content = browser_page.locator('body').inner_text()
        for required in ('95', '2,007,012', '25,440', '8,064', '38.19 ms', '82.9%', '5/8', 'Partially fulfilled', 'Suricata alone', 'not production authentication'):
            if required not in text_content:
                raise ValueError(f'Required report fact is missing: {required}')
        for index in (0, 3, 4, 5, 8, 10, 12, 14):
            browser_page.locator('.sheet').nth(index).screenshot(path=str(previews / f'page-{index+1:02}.png'))
        browser.close()
    pdf_bytes = PDF.read_bytes()
    actual_pages = len(re.findall(rb'/Type\s*/Page\b', pdf_bytes))
    if actual_pages != len(pages) or not pdf_bytes.startswith(b'%PDF-') or b'%%EOF' not in pdf_bytes[-100:]:
        raise ValueError(f'PDF structure/page count mismatch: {actual_pages} instead of {len(pages)}')
    verify_hashes(sources)
    output = dict(passed=True, report=PDF.relative_to(ROOT).as_posix(), pages=actual_pages,
                  generated_local=datetime.now().astimezone().isoformat(),
                  pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(), input_sha256=sources,
                  retained_source_and_evidence_hashes_verified=True,
                  no_page_overflow=True, layout=layout,
                  scope='Document generation and evidence-integrity checks; experiments were not rerun')
    (OUT / 'MIS5_Improvements_Explained.validation.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps({key:value for key,value in output.items() if key not in ('input_sha256','layout')}, indent=2))


if __name__ == '__main__':
    run()

"""Build the current report from verified artifacts; never invent missing results."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'


def run():
    def read(name):return json.loads((OUT/name).read_text())
    evaluation=read('evaluation.json');audit=read('audit.json')
    suite=read('test_suite_verification.json');stress=read('stress_validation.json');metrics=read('metrics_verification.json')
    frontend=read('frontend_verification.json');operations_ui=read('operations_ui_verification.json')
    for result in (suite,stress,metrics,frontend,operations_ui):
        if result['passed'] is not True:raise ValueError('Current checks have not passed')
        for relative,digest in result.get('source_sha256',{}).items():
            if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise ValueError(f'Stale check: {relative}')
    for relative,digest in {**metrics['input_sha256'],**metrics['archive_sha256']}.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise ValueError(f'Stale metric evidence: {relative}')
    frozen=json.loads((ROOT/'experiments/current_version/reproducibility.json').read_text())['sha256']
    frozen_checks=0
    for relative,digest in frozen.items():
        if relative.replace('\\','/').startswith('experiments/current_version/'):
            if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise ValueError(f'Changed frozen evidence: {relative}')
            frozen_checks+=1
    verification=dict(backend=dict(passed=True,tests=suite['tests'],details='test_suite_verification.json'),
                      frontend=dict(passed=True,details='frontend_verification.json'),
                      stress=dict(passed=True,experts=stress['experts'],forecast_values=stress['forecast_values_checked'],details='stress_validation.json'),
                      independent_metrics=dict(passed=True,score_rows=metrics['total_score_rows'],aggregate_rows=metrics['aggregate_rows'],
                                               validation_thresholds=metrics['validation_thresholds_checked'],details='metrics_verification.json'),
                      frozen_files_unchanged=frozen_checks,
                      deployment_scope='Local replay and fault injection; no production attack prevention measured')
    selection=read('selection_verification.json');benchmark=read('live_benchmark.json');ui=read('ui_verification.json')
    if not (audit['passed'] and selection['passed'] and verification['backend']['passed'] and ui['passed']):
        raise ValueError('Verification has not passed; refusing a verified-release report')
    for relative,digest in audit['source_sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise ValueError(f'Stale audit: {relative}')
    for relative,digest in read('selection_inputs.json').items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise ValueError(f'Stale selection: {relative}')
    full='aminer+suricata+wazuh'
    rows=[r for r in evaluation['summary'] if r['available']==full]
    paired=benchmark['paired_inference_optimization']
    if not paired['predictions_identical']:raise ValueError('Optimized inference differs from reference')
    table=[]
    for row in sorted(rows,key=lambda r:r['horizon'],reverse=True):
        for key,label in (('baseline','Responsive (default)'),('improved','Confirmed (optional)')):
            value=row[key]
            table.append(f"| {row['horizon']} min | {label} | {value['timely_notification']}/8 | {value['false_warning_episodes']} | {value['notifications']} | {value['mean_notification_lead_minutes']:.2f} min |")
    lines=[
        '# Current verified runtime release','',
        'This release prioritizes original warning responsiveness, reduces redundant computation,',
        'and makes the quieter alternative explicit. It does not claim a universally best model',
        'or flawless production performance. Forecast weights, calibration and thresholds are unchanged.','',
        '## Active behavior','',
        '* `responsive` is the live default: immediate threshold warnings with no added confirmation or notification cooldown.',
        '* `confirmed` is optional: two-bucket confirmation and bounded episode handling reduce notifications at the cost of possible delays or missed brief signals.',
        '* All seven healthy expert histories remain available for sensor fallback. Only the selected expert computes a forecast.',
        '* Missing/stale sensors route to the matching original expert; complete outage abstains. Model status validates package integrity.',
        '* The validation-selected candidate remains research-only because it failed to preserve all measured lead constraints.','',
        '## Verified campaign results','',
        '| Horizon | Profile | Timely campaigns | False warning episodes | Notifications | Mean notification lead |',
        '|---|---|---:|---:|---:|---:|',*table,'',
        f"The responsive policy exactly matches original warning and notification traces in all {audit['responsive_matches_original_cases']} fixed-availability campaign/sensor/horizon cases.",
        'The optional confirmed profile retains its 30-minute alarm benefit, but its first timely notification is later on four of five warned campaigns, including a ten-minute delay on fox.',
        'At 15 minutes its coverage is lower. These are previously inspected campaigns, not independent confirmation.',
        '“False” refers to the target time window and does not necessarily mean benign traffic. Brier prediction error is unchanged.','',
        '## Inference performance','',
        f"A same-process paired comparison used {paired['previous_eager']['samples']} archived minute buckets and identical fitted experts:",'',
        '| Measurement | Previous eager reference | Selected-expert computation |',
        '|---|---:|---:|',
        f"| Median inference | {paired['previous_eager']['median_ms']:.2f} ms | {paired['current_selected_only']['median_ms']:.2f} ms |",
        f"| p95 inference | {paired['previous_eager']['p95_ms']:.2f} ms | {paired['current_selected_only']['p95_ms']:.2f} ms |",'',
        f"Median inference computation falls by **{paired['median_reduction_percent']:.1f}%**, with exactly identical selected forecast probabilities. The comparison includes causal history updates; it excludes sensor collection and HTTP.",'',
        f"The separate running-service replay processed {benchmark['observations']} observations with **{benchmark['http_round_trip']['p95_ms']:.2f} ms p95 HTTP round trip**.",
        f"It used the responsive profile and recorded {benchmark['receipts_acknowledged']}/{benchmark['notifications']} notification receipts and {benchmark['noop_handlers_completed']} no-op completions.",
        'These receipt counts and timings do not demonstrate attack prevention. The earlier HTTP run is preserved in `live_benchmark_pre_optimization.json`; differences between separate HTTP runs are not a controlled speedup estimate.','',
        '## Candidate selection and release decision','',
        f"Eleven candidate policies were evaluated in {selection['cases']} original fold/sensor/horizon settings. Choices used outer-validation forecasts and endpoints only, with fixed original thresholds.",
        'Eligibility required no validation loss in coverage or first lead and no increase in false notifications, false warning episodes, negative warning minutes or total notifications.',
        f"The resulting selector had lead regressions in {len(selection['test_regressions'])} subsequent evaluation settings and was **not promoted**. The default does not change behavior by campaign identity.",
        'The candidate set and these campaigns have been inspected during development. Reusing the original validation campaign for threshold and policy selection is not a new independent split.',
        'See `SELECTION_PROTOCOL.md`, `policy_selection.json` and `selection_verification.json`; every candidate and observed regression is retained.','',
        '## Quality checks and remaining limits','',
        f"* Backend: {verification['backend']['tests']} tests pass.",
        '* Frontend: production build, lint (no warnings), desktop/mobile checks, replay controls and reordered-reply browser checks pass.',
        f"* Independent reconstruction: {audit['paired_campaign_horizon_sensor_checks']} campaign/sensor/horizon cases and {audit['aggregate_checks']} aggregates pass.",
        '* All seven model experts match their frozen forecasts exactly; changing-outage stream/batch checks, poisoned unavailable input and recovery checks pass.',
        '* The database connection leak found in verification is fixed; model readiness rejects missing, corrupt or unloadable packages.',
        '* Sensor-error gains remain existing experts versus naive zero-fill on one inspected fold. Fresh-campaign dynamic-outage accuracy is not established.',
        '* No production sensor feed or defensive actuator was connected. Real mitigation effectiveness, production load behavior and independent generalization remain unmeasured.',
        '* Stream state is process-local and resets on restart. Source health must describe a complete collector path; a heartbeat cannot expose silent partial loss inside a sensor reported healthy.','',
        'For setup and profile selection, read [the runbook](../../docs/OPERATIONAL_IMPROVEMENTS.md).',
        'The confirmed-profile study is retained in [REPORT.md](REPORT.md), with the original caveats.',''
    ]
    lines += [
        '## Thorough local validation and fixes','',
        f"* All {stress['experts']} refitted experts across eight campaigns reproduce {stress['forecast_values_checked']:,} saved forecast values with zero error. Stream prefixes remain causal and test labels cannot affect inference.",
        f"* {stress['operation_observations']:,} API observations exercise all sensor subsets, stale/missing heartbeats, outages, recovery, gaps, extreme counts, unknown detectors and poisoned unavailable-sensor counts.",
        f"* {metrics['total_score_rows']:,} score rows, {metrics['aggregate_rows']:,} aggregate rows and {metrics['validation_thresholds_checked']:,} threshold choices were independently reconstructed. Threshold optimality is restricted to the original declared validation grid and constraints.",
        f"* {frozen_checks} frozen-package files retain their original checksums. Dashboard evidence is checked before content-keyed cache access; corruption or incomplete evidence produces a 503 instead of a stale verified result.",
        '* Exact most-recent observation retries return the committed result and notification ID. Changed evidence at the same timestamp conflicts. Failed inference or notification persistence rolls temporal and warning state back so the bucket can be retried.',
        '* The local API rejects remote peers, cross-site browser requests, forged hosts, ambiguous lengths, oversized/slow bodies and invalid schemas. Validation responses omit rejected values. This is a loopback research service, not production authentication.',
        '* Legacy individual streams have separate client cookies; historical batches own independent state. SQL identifiers are allowlisted, generation is bounded, and an empty synthetic run replaces only its own rows. Legacy temporal history is bounded.',
        '* Legacy action ranking now uses unrounded utility; an action compared with itself has identical illustrative loss curves. Both chart series use the same scale. Browser controls prevent stale scenario, mode, horizon or action responses replacing newer results.',
        '* Live action costs account for forecast age within the original observation-based 30-minute window. Linear CDF interpolation between saved horizons is an explicit modeling assumption. Historical replay retains its original formula.',
        '* Completed/failed receipts are immutable, retries preserve the first timing and notes, and backwards-clock receipts are rejected. Failed responses now have resolution timing.',
        '* Model packages receive structural/probability checks after checksum validation. Pickle remains trusted local code: manifests are not signatures, and a hostile local writer is outside this protection.',
        '* A narrow source scan found no matching private-key/API-key patterns outside excluded data and private folders. This is not an exhaustive credential or dependency-vulnerability audit.',
        '', '## Costs and limits of the fixes','',
        f"The final HTTP replay measured {benchmark['http_round_trip']['median_ms']:.2f} ms median, {benchmark['http_round_trip']['p95_ms']:.2f} ms p95 and {benchmark['http_round_trip']['max_ms']:.2f} ms maximum. It includes validation, transactional checkpoints and receipt persistence. Earlier separate runs are retained and are not interchangeable with this measurement; no end-to-end speedup is claimed.",
        'The default still warns on 5/8 of these campaigns at 30 minutes. Suppressing more alarms can miss or delay warnings; complete sensor loss still requires abstention. Bounds intentionally reject excessive requests. Sessions and idempotency are process-local, and only the most recent observation has an idempotent replay cache; restart or multi-worker recovery is not implemented.',
        'Response effects and monetary savings have not been observed. Existing cached legacy RQ reports may predate the corrected simulation and are labeled separately in the UI. Python emitted existing optional dependency/deprecation/core-detection warnings during checks; passing tests do not imply a warning-free environment or an exhaustive security assessment.',
        'These tests establish the stated local properties. They cannot establish flawless behavior, a globally optimal architecture, or success against every future attack.',''
    ]
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    (OUT/'CURRENT_RELEASE.md').write_text('\n'.join(lines),encoding='utf-8')
    sources=[ROOT/'backend/app/models/warning_policy.py',ROOT/'backend/app/models/warning_profiles.py',
             ROOT/'backend/app/routers/live_router.py',ROOT/'backend/app/ingestion/database.py',
             ROOT/'backend/research/streaming_forecast.py',ROOT/'backend/research/select_warning_policy.py',
             ROOT/'backend/research/evaluate_selected_policy.py',ROOT/'backend/research/verify_selected_policy.py',
             ROOT/'backend/tests/test_warning_selection.py',ROOT/'backend/tests/test_operational_improvements.py',
             ROOT/'frontend/src/OperationalResults.tsx',Path(__file__)]
    decision=dict(default_warning_profile='responsive',confirmed_profile='optional',selector_promoted=False,
                  reason='Preserve original warning traces; candidate selection did not preserve every evaluation constraint',
                  inference_predictions_identical=True,production_mitigation_effectiveness_verified=False,
                  source_sha256={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
                  artifact_sha256={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in OUT.glob('*.json') if path.name!='release_decision.json'})
    (OUT/'release_decision.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
    print(f'Wrote current release: {verification["backend"]["tests"]} tests, {paired["median_reduction_percent"]:.1f}% less median inference time, unchanged predictions')


if __name__=='__main__':run()

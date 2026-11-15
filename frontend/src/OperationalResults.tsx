import { useEffect, useState } from "react";

type Metrics = {
  timely_notification: number; false_notifications: number; false_warning_episodes: number;
  negative_warning_minutes: number; notifications: number; mean_notification_lead_minutes: number | null;
};
type Summary = { available: string; horizon: number; campaigns: number; baseline: Metrics; improved: Metrics };
type Candidate = { available: string; horizon: number; selected: Metrics; test_regressions: { campaign: string; metrics: string[] }[] };
type Report = {
  summary: Summary[]; default_warning_profile: string;
  candidate_evaluation: null | { summary: Candidate[] };
  benchmark: null | {
    http_round_trip: { p95_ms: number }; observations: number; receipts_acknowledged: number; notifications: number;
    paired_inference_optimization?: { median_reduction_percent: number; predictions_identical: boolean };
  };
};

export default function OperationalResults({ horizon, available }: { horizon: number; available: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/live/report", { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error("Operational results are unavailable. Check that the local service is running.");
      return response.json();
    }).then(setReport).catch(error => { if (error.name !== "AbortError") setError(error.message); });
    return () => controller.abort();
  }, []);
  const row = report?.summary.find(r => r.available === available && r.horizon === horizon);
  const candidate = report?.candidate_evaluation?.summary.find(r => r.available === available && r.horizon === horizon);
  const cells = (m: Metrics, campaigns: number) => <>
    <td>{m.timely_notification}/{campaigns}</td><td>{m.false_notifications}</td><td>{m.false_warning_episodes}</td>
    <td>{m.notifications}</td><td>{m.negative_warning_minutes}</td>
    <td>{m.mean_notification_lead_minutes === null ? "No timely warning" : `${m.mean_notification_lead_minutes.toFixed(2)} min`}</td>
  </>;
  return <section className="research-panel">
    <div className="panel-heading"><div><h2>Operational improvements</h2><p>Default: immediate warnings. The quieter confirmed profile is optional. Historical model results follow below.</p></div><a className="quiet-button" href="/api/live/report" target="_blank" rel="noreferrer">Evaluation JSON</a></div>
    {error && <p role="alert">{error}</p>}
    {!report && !error && <p role="status">Loading operational evaluation…</p>}
    {row && <>
      <div className="table-wrap"><table>
        <thead><tr><th>Warning profile</th><th>Timely coverage</th><th>False notifications</th><th>False episodes</th><th>All notifications</th><th>Negative warning minutes</th><th>Mean notification lead</th></tr></thead>
        <tbody>
          <tr className="highlight-row"><td>Responsive · default / original timing</td>{cells(row.baseline, row.campaigns)}</tr>
          <tr><td>Confirmed · fewer notifications</td>{cells(row.improved, row.campaigns)}</tr>
        </tbody>
      </table></div>
      <p className="panel-note">Responsive warnings preserve original threshold coverage and first-alert timing. Confirmed warnings require two consecutive minute buckets, use bounded hysteresis and a five-minute notification cooldown. They can miss brief signals or notify later. Forecast probability error is unchanged.</p>
      {row.improved.timely_notification < row.baseline.timely_notification && <p className="research-message">The confirmed profile loses coverage at this horizon and sensor setting. It is not the default.</p>}
      <p className="panel-note">“False” means outside the target outcome window; it does not necessarily mean benign traffic. A higher mean lead can hide delays on individual campaigns.</p>
      {candidate && <details><summary>Validation-selected candidate · research only</summary>
        <p className="panel-note">Candidates were selected on validation forecasts with coverage, lead and alarm-burden constraints. They did not preserve every constraint on the subsequent campaign evaluations, so the selector was not promoted to the live default.</p>
        <p className="panel-note">This setting: {candidate.selected.timely_notification}/{row.campaigns} timely campaigns, {candidate.selected.false_notifications} false notifications. {candidate.test_regressions.length ? `Observed regressions: ${candidate.test_regressions.map(r => r.campaign).join(", ")}.` : "No individual constraint regression in this setting; the overall candidate still failed promotion."}</p>
      </details>}
    </>}
    {report?.benchmark && <>
      <p className="panel-note">Local HTTP test: {report.benchmark.observations} archived observations · p95 round trip {report.benchmark.http_round_trip.p95_ms.toFixed(1)} ms · {report.benchmark.receipts_acknowledged}/{report.benchmark.notifications} test notifications acknowledged. Sensor fallback and recovery were verified. Response receipts used a no-op handler; actual attack prevention remains unmeasured.</p>
      {report.benchmark.paired_inference_optimization && <p className="panel-note">Paired inference check: {report.benchmark.paired_inference_optimization.median_reduction_percent.toFixed(1)}% less median computation time with identical forecasts. This comparison excludes sensor collection and network time.</p>}
    </>}
  </section>;
}

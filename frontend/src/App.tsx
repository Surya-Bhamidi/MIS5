import { useCallback, useEffect, useState } from "react";
import { Activity, ArrowRight, CheckCircle2, Download, FlaskConical, Layers, Pause, Play, RotateCcw, Shield, SkipForward } from "lucide-react";
import LegacyDashboard from "./LegacyDashboard";
import OperationalResults from "./OperationalResults";
import "./research.css";

type Score = { strict_warning_recall: number; strict_lead_minutes: number | null; false_warning_episodes: number; brier: number; average_precision: number };
type Model = { mode: string; label: string; color: string; strict_warned: number; campaigns: number; mean_brier: number; mean_ap: number; false_episodes: number };
type Campaign = { name: string; hybrid: Score; counts: Score };
type Overview = { status: string; verified?: boolean; regression_tests?: number; models: Model[]; campaigns: Campaign[]; sensors: string[] };
type Point = { timestamp: number; minutes_before: number; risk: number[]; warning: boolean; episode_start: boolean; recommended_action: string; modeled_losses: number[] };
type Replay = { status: string; points: Point[]; horizons: number[]; threshold: number; endpoint: number; actions: string[]; score: Score };
type Tab = "overview" | "replay" | "method";
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const pretty = (s: string) => s === "none" ? "No sensors (abstain)" : s.split("+").map(v => ({ aminer: "AMiner", suricata: "Suricata", wazuh: "Wazuh" }[v] || v)).join(" + ");
const utc = (t: number) => new Date(t * 1000).toLocaleString("en-GB", { timeZone: "UTC", hour12: false }) + " UTC";

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`/api/research/${path}`, { signal });
  if (!response.ok) throw new Error(`Could not load research results (HTTP ${response.status}). Check the local API.`);
  return response.json();
}

function RiskChart({ data, horizon, index, onSelect }: { data: Replay; horizon: number; index: number; onSelect: (i: number) => void }) {
  const points = data.points;
  const hi = data.horizons.indexOf(horizon);
  const width = 960, height = 300, left = 52, right = 28, top = 22, bottom = 45;
  const span = points[0].minutes_before - points[points.length - 1].minutes_before || 1;
  const x = (p: Point) => left + (points[0].minutes_before - p.minutes_before) / span * (width - left - right);
  const y = (v: number) => top + (1 - v) * (height - top - bottom);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p)},${y(p.risk[hi])}`).join(" ");
  const current = points[index];
  return <svg className="risk-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${horizon}-minute archived risk forecast. Click to inspect a minute.`}
    onClick={e => { const rect = e.currentTarget.getBoundingClientRect(); const at = ((e.clientX - rect.left) / rect.width * width - left) / (width - left - right); onSelect(Math.max(0, Math.min(points.length - 1, Math.round(at * (points.length - 1))))); }}>
    <defs><linearGradient id="risk-fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#2dd4bf" stopOpacity=".25"/><stop offset="1" stopColor="#2dd4bf" stopOpacity="0"/></linearGradient></defs>
    {[0, .25, .5, .75, 1].map(v => <g key={v}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} stroke="#233146"/><text x={left-12} y={y(v)+4} textAnchor="end" fill="#8ca0ba" fontSize="12">{Math.round(v*100)}%</text></g>)}
    <path d={`${path} L${x(points[points.length-1])},${y(0)} L${x(points[0])},${y(0)} Z`} fill="url(#risk-fill)"/>
    {data.threshold <= 1 && <><line x1={left} x2={width-right} y1={y(data.threshold)} y2={y(data.threshold)} stroke="#fbbf24" strokeDasharray="5 5"/><text x={width-right} y={y(data.threshold)-7} fill="#fbbf24" fontSize="12" textAnchor="end">Warning threshold {pct(data.threshold)}</text></>}
    <path d={path} stroke="#2dd4bf" strokeWidth="2.5" fill="none"/>
    {points.filter(p => p.episode_start).map(p => <circle key={p.timestamp} cx={x(p)} cy={y(p.risk[hi])} r="5" fill="#fbbf24"><title>New warning: {p.minutes_before.toFixed(1)} minutes before outcome</title></circle>)}
    <line x1={x(current)} x2={x(current)} y1={top} y2={height-bottom} stroke="#dbeafe" strokeDasharray="3 4" opacity=".6"/>
    <circle cx={x(current)} cy={y(current.risk[hi])} r="5" fill="#f8fafc" stroke="#2dd4bf" strokeWidth="2"/>
    {[0, .25, .5, .75, 1].map(f => <text key={f} x={left+f*(width-left-right)} y={height-18} fill="#8ca0ba" fontSize="12" textAnchor="middle">{(points[0].minutes_before-f*span).toFixed(0)} min before</text>)}
  </svg>;
}

export default function App() {
  const [tab, changeTab] = useState<Tab>("overview");
  const [legacy, changeLegacy] = useState(false);
  const [horizon, changeHorizon] = useState(30);
  const [available, changeAvailable] = useState("aminer+suricata+wazuh");
  const [campaign, changeCampaign] = useState("fox");
  const overviewKey = JSON.stringify([horizon, available]);
  const replayKey = JSON.stringify([campaign, horizon, available]);
  const [overviewResponse, setOverviewResponse] = useState<{ key: string; data: Overview } | null>(null);
  const [replayResponse, setReplayResponse] = useState<{ key: string; data: Replay } | null>(null);
  const [overviewFailure, setOverviewFailure] = useState<{ key: string; message: string } | null>(null);
  const [replayFailure, setReplayFailure] = useState<{ key: string; message: string } | null>(null);
  const [playback, updatePlayback] = useState({ key: "", index: 0, requested: false });
  const overview = overviewResponse?.key === overviewKey ? overviewResponse.data : null;
  const replay = tab === "replay" && replayResponse?.key === replayKey ? replayResponse.data : null;
  const error = overviewFailure?.key === overviewKey ? overviewFailure.message : "";
  const replayError = replayFailure?.key === replayKey ? replayFailure.message : "";
  const index = playback.key === replayKey ? Math.min(playback.index, Math.max(0, (replay?.points.length || 1) - 1)) : 0;
  const playing = !legacy && playback.key === replayKey && playback.requested && index < (replay?.points.length || 0) - 1;
  const resetView = () => { updatePlayback(p => ({ ...p, index: 0, requested: false })); };
  const setTab = (value: Tab) => { resetView(); changeTab(value); };
  const setLegacy = (value: boolean) => { resetView(); changeLegacy(value); };
  const setHorizon = (value: number) => { resetView(); changeHorizon(value); };
  const setAvailable = (value: string) => { resetView(); changeAvailable(value); };
  const setCampaign = (value: string) => { resetView(); changeCampaign(value); };
  const setIndex = useCallback((value: number | ((index: number) => number)) => updatePlayback(previous => ({
    key: replayKey, index: typeof value === "function" ? value(previous.key === replayKey ? previous.index : 0) : value,
    requested: previous.key === replayKey && previous.requested,
  })), [replayKey]);
  const setPlaying = (requested: boolean) => updatePlayback(previous => ({ key: replayKey, index: previous.key === replayKey ? previous.index : 0, requested }));
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    get<Overview>(`overview?horizon=${horizon}&available=${encodeURIComponent(available)}`, controller.signal).then(data => { if (active) { setOverviewResponse({ key: overviewKey, data }); setOverviewFailure(previous => previous?.key === overviewKey ? null : previous); } }).catch(e => { if (active && e.name !== "AbortError") setOverviewFailure({ key: overviewKey, message: e.message }); });
    return () => { active = false; controller.abort(); };
  }, [horizon, available, overviewKey]);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    if (tab === "replay" && !legacy) get<Replay>(`replay/${campaign}?horizon=${horizon}&available=${encodeURIComponent(available)}`, controller.signal).then(data => { if (active) { setReplayResponse({ key: replayKey, data }); setReplayFailure(previous => previous?.key === replayKey ? null : previous); } }).catch(e => { if (active && e.name !== "AbortError") setReplayFailure({ key: replayKey, message: e.message }); });
    return () => { active = false; controller.abort(); };
  }, [tab, campaign, horizon, available, replayKey, legacy]);
  useEffect(() => {
    if (!playing || !replay?.points.length) return;
    const timer = window.setInterval(() => setIndex(i => Math.min(i + speed, replay.points.length - 1)), 500);
    return () => window.clearInterval(timer);
  }, [playing, replay, speed, setIndex]);
  const hybrid = overview?.models.find(m => m.mode === "pooled_fixed_blend");
  const matched = overview?.models.find(m => m.mode === "pooled_counts");
  const point = replay?.points[index];
  const hi = replay?.horizons.indexOf(horizon) ?? 0;
  const inspect = (name: string) => { setCampaign(name); setTab("replay"); };
  if (legacy) return <><div className="legacy-notice"><span>Earlier DARPA / synthetic demo · separate from the current AIT research results</span><button onClick={() => setLegacy(false)}>Back to current research <ArrowRight size={15}/></button></div><LegacyDashboard/></>;
  return <div className="research-app">
    <header className="research-header"><a className="research-brand" href="#" onClick={e => { e.preventDefault(); setTab("overview"); }}><span className="brand-shield"><Shield size={23}/></span><span><strong>MIS5</strong><small>Cyberattack early warning</small></span></a><div className="header-status"><span className="status-dot"/> Archived AIT evaluation</div><button className="quiet-button" onClick={() => setLegacy(true)}>Earlier demo <ArrowRight size={15}/></button></header>
    <main className="research-main">
      <div className="research-intro"><div><div className="eyebrow">MULTI-SENSOR · PROBABILISTIC FORECASTING</div><h1>Earlier warnings. Clearer evidence.</h1><p>Explore the fixed hybrid’s forecasts before successful root access, and the tradeoffs behind its results.</p></div><span className="preset-badge"><Layers size={16}/> 75% counts + 25% state branch</span></div>
      <div className="research-toolbar"><nav aria-label="Dashboard"><button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}><FlaskConical size={17}/> Results overview</button><button className={tab === "replay" ? "active" : ""} onClick={() => setTab("replay")}><Activity size={17}/> Campaign replay</button><button className={tab === "method" ? "active" : ""} onClick={() => setTab("method")}><Layers size={17}/> Method & plots</button></nav><div className="research-controls"><label>Horizon<select aria-label="Horizon" value={horizon} onChange={e => setHorizon(Number(e.target.value))}><option value={30}>30 minutes · primary</option><option value={15}>15 minutes</option></select></label><label>Sensor inputs<select aria-label="Sensor inputs" value={available} onChange={e => setAvailable(e.target.value)}>{(overview?.sensors || ["aminer+suricata+wazuh", "aminer+suricata", "aminer+wazuh", "suricata+wazuh", "aminer", "suricata", "wazuh", "none"]).map(v => <option value={v} key={v}>{pretty(v)}</option>)}</select></label></div></div>
      {error && <div className="research-message error" role="alert">{error}<button onClick={() => window.location.reload()}>Retry</button></div>}
      {!overview && !error && <div className="research-message" role="status">Loading verified research results…</div>}
      {overview?.status === "insufficient_sensors" && <div className="research-message"><Shield size={21}/><div><strong>Insufficient sensor evidence</strong><p>No forecast or response is recommended when all sensor inputs are unavailable. Choose an available sensor configuration.</p></div></div>}
      {tab === "overview" && overview && hybrid && matched && <>
        <OperationalResults horizon={horizon} available={available}/>
        <div className="metric-grid"><article className="metric-card primary"><span>Timely-warning coverage</span><strong>{pct(hybrid.strict_warned / hybrid.campaigns)}</strong><p>{hybrid.strict_warned}/{hybrid.campaigns} campaigns · matched counts {matched.strict_warned}/{matched.campaigns}</p><small>{((hybrid.strict_warned-matched.strict_warned)/hybrid.campaigns*100).toFixed(1)} percentage-point difference</small></article><article className="metric-card"><span>Probability error · Brier × 1,000</span><strong>{(hybrid.mean_brier*1000).toFixed(4)}</strong><p>Matched counts {(matched.mean_brier*1000).toFixed(4)}</p><small>Lower is better · {Math.abs(100*(1-hybrid.mean_brier/matched.mean_brier)).toFixed(2)}% {hybrid.mean_brier < matched.mean_brier ? "lower" : "higher"} error</small></article><article className="metric-card"><span>False-alarm episodes</span><strong className="amber">{hybrid.false_episodes}</strong><p>Matched counts {matched.false_episodes}</p><small>Separate warning periods · lower is better</small></article><article className="metric-card"><span>Average precision</span><strong>{hybrid.mean_ap.toFixed(4)}</strong><p>Matched counts {matched.mean_ap.toFixed(4)}</p><small>Ranking quality · higher is better</small></article></div>
        <div className="overview-grid"><section className="research-panel"><div className="panel-heading"><div><h2>{horizon}-minute model comparison</h2><p>All models below are versions implemented in this project.</p></div><a className="quiet-button" href="/api/research/assets/metrics.csv"><Download size={15}/> CSV</a></div><div className="table-wrap"><table><thead><tr><th>Model</th><th>Timely coverage ↑</th><th>Brier × 1,000 ↓</th><th>False episodes ↓</th><th>AP ↑</th></tr></thead><tbody>{overview.models.map(m => <tr key={m.mode} className={m.mode === "pooled_fixed_blend" ? "highlight-row" : ""}><td><span className="model-dot" style={{ background: m.color }}/>{m.label}</td><td><div className="coverage-cell"><span>{m.strict_warned}/{m.campaigns}</span><div className="coverage-track"><i style={{ width: `${m.strict_warned/m.campaigns*100}%`, background: m.color }}/></div></div></td><td>{(m.mean_brier*1000).toFixed(4)}</td><td>{m.false_episodes}</td><td>{m.mean_ap.toFixed(4)}</td></tr>)}</tbody></table></div><p className="panel-note">Matched counts uses the same pooled calibration procedure. Coverage measures timely new warnings, not classification accuracy.</p></section><section className="research-panel finding"><span className="eyebrow">WHAT THE RESULTS SUPPORT</span><h2>{hybrid.strict_warned > matched.strict_warned ? "Higher timely-warning coverage" : "Coverage does not settle the comparison"}</h2><p>At this horizon and sensor setting, the hybrid warns on <strong>{hybrid.strict_warned}</strong> campaigns versus <strong>{matched.strict_warned}</strong> for matched counts, with <strong>{hybrid.false_episodes}</strong> versus <strong>{matched.false_episodes}</strong> false episodes.</p><p>Neither architecture wins every metric. Treat this as exploratory evidence from eight previously inspected campaigns.</p><div className="finding-rule">Validation budget: 1 false episode per 24 negative hours and at most 5 negative warning minutes. Test alarm rates can exceed that budget.</div></section></div>
        <section className="research-panel"><div className="panel-heading"><div><h2>Campaign outcomes</h2><p>A new warning must start within {horizon} minutes before the verified root outcome.</p></div><span className="small-tag">8 campaign folds</span></div><div className="campaign-grid">{overview.campaigns.map(c => <button className="campaign-card" key={c.name} onClick={() => inspect(c.name)}><div><strong>{c.name}</strong><ArrowRight size={15}/></div><span className={`outcome ${c.hybrid.strict_warning_recall ? "success" : "missed"}`}>{c.hybrid.strict_warning_recall ? `${c.hybrid.strict_lead_minutes?.toFixed(1)} min lead` : "No timely new warning"}</span><small>{c.hybrid.false_warning_episodes} false episodes · matched {c.counts.strict_warning_recall ? "warned" : "missed"}</small></button>)}</div></section>
      </>}
      {tab === "replay" && overview?.status === "ok" && <>
        <section className="research-panel"><div className="panel-heading"><div><h2>Campaign forecast replay</h2><p>Saved pre-outcome predictions; playback does not retrain the model or execute a defense.</p></div><label className="campaign-select">Campaign<select aria-label="Campaign" value={campaign} onChange={e => setCampaign(e.target.value)}>{overview.campaigns.map(c => <option key={c.name}>{c.name}</option>)}</select></label></div>
          {replayError && <p className="research-message error" role="alert">{replayError}</p>}
          {!replay && !replayError && <p className="research-message">Loading archived forecasts…</p>}
          {replay && point && <><div className="replay-top"><div><span className={`outcome ${point.warning ? "warning" : "neutral"}`}>{point.warning ? "Warning threshold crossed" : "Below warning threshold"}</span><strong>{pct(point.risk[hi])}<small>risk within {horizon} minutes</small></strong></div><div className="replay-time"><strong>{point.minutes_before.toFixed(1)} min before outcome</strong><small>{utc(point.timestamp)}</small></div></div><RiskChart data={replay} horizon={horizon} index={index} onSelect={i => { setPlaying(false); setIndex(i); }}/><div className="playback-controls"><button className="action-button" aria-label={playing ? "Pause replay" : "Play replay"} onClick={() => { if (!playing && index === replay.points.length-1) setIndex(0); setPlaying(!playing); }}>{playing ? <Pause size={17}/> : <Play size={17}/>} {playing ? "Pause" : "Play"}</button><button className="quiet-button" onClick={() => { setPlaying(false); setIndex(0); }}><RotateCcw size={16}/> Reset</button><button className="quiet-button" aria-label="Step forward" onClick={() => { setPlaying(false); setIndex(Math.min(index+1, replay.points.length-1)); }}><SkipForward size={17}/></button><input aria-label="Replay minute" type="range" min={0} max={replay.points.length-1} value={index} onChange={e => { setPlaying(false); setIndex(Number(e.target.value)); }}/><select aria-label="Playback speed" value={speed} onChange={e => setSpeed(Number(e.target.value))}><option value={1}>1×</option><option value={5}>5×</option><option value={15}>15×</option></select><button className="quiet-button" onClick={() => { const first = replay.points.findIndex(p => p.episode_start && p.minutes_before <= horizon); if (first >= 0) { setPlaying(false); setIndex(first); } }} disabled={!replay.points.some(p => p.episode_start && p.minutes_before <= horizon)}>Jump to timely warning</button></div><p className="panel-note">Yellow dots mark new warning starts. Root outcome: {utc(replay.endpoint)} (retrospective evaluation marker). {replay.threshold > 1 ? "Validation selected an abstaining threshold above 100%." : `Frozen threshold: ${pct(replay.threshold)}.`}</p></>}
        </section>
        {replay && point && <div className="replay-details"><section className="research-panel"><div className="panel-heading"><div><h2>Forecast by horizon</h2><p>Probability of the target outcome within each future window.</p></div></div><div className="horizon-grid">{replay.horizons.map((h, j) => <div key={h} className={h === horizon ? "selected" : ""}><span>{h} min</span><strong>{pct(point.risk[j])}</strong></div>)}</div></section><section className="research-panel"><div className="panel-heading"><div><h2>Modeled response recommendation</h2><p>Uses the saved probabilities and assumed costs; no action is executed.</p></div></div><div className="recommendation"><Shield size={22}/><strong>{point.recommended_action}</strong><span>Lowest modeled expected loss</span></div><div className="loss-grid">{replay.actions.map((action, j) => <div key={action}><span>{action}</span><strong>{point.modeled_losses[j].toFixed(3)}</strong></div>)}</div><p className="panel-note">Assumptions: damage 20; effectiveness multiplier 0.8; disruption multiplier 1. Response delay is included. These are model units, not measured money or prevention benefits.</p></section></div>}
      </>}
      {tab === "method" && <>
        <section className="research-panel"><div className="panel-heading"><div><h2>How the current hybrid works</h2><p>Past-only evidence feeds a fixed blend at all six forecast horizons.</p></div></div><div className="pipeline-grid">{[{ unit: "INPUT", title: "Multi-sensor history", detail: "Detector counts and trailing 5-, 15- and 60-minute averages from AMiner, Suricata and Wazuh." }, { unit: "UNIT 1", title: "Bayesian evidence", detail: "Observation likelihood relates detector evidence to latent attack stages and omits unavailable sensors." }, { unit: "UNIT 2", title: "Temporal state estimates", detail: "Forward HMM filtering estimates stage probabilities using only evidence available up to that minute." }, { unit: "FORECAST", title: "Fixed hybrid + calibration", detail: "75% counts-only risk plus 25% counts-and-state risk, followed by campaign-pooled probability calibration." }, { unit: "UNIT 3", title: "Response decisions", detail: "A Decision Network compares assumed damage, disruption, effectiveness and response delays." }].map(p => <article key={p.unit}><span className="eyebrow">{p.unit}</span><h3>{p.title}</h3><p>{p.detail}</p></article>)}</div></section>
        <section className="research-panel"><div className="panel-heading"><div><h2>Presentation plots</h2><p>Full-sensor, 30-minute figures. They stay fixed when the dashboard filters change.</p></div></div><div className="plot-grid">{[["01_timely_warning_coverage", "Timely-warning coverage"], ["02_probability_error", "Probability error"], ["03_alarm_tradeoff", "Coverage–alarm tradeoff"]].map(([name, title]) => <article key={name}><a href={`/api/research/assets/${name}.png`} target="_blank" rel="noreferrer"><img src={`/api/research/assets/${name}.png`} alt={title}/></a><div><strong>{title}</strong><a href={`/api/research/assets/${name}.pdf`}><Download size={14}/> PDF</a></div></article>)}</div></section>
        <section className="research-panel"><div className="panel-heading"><div><h2>Scope and validation</h2><p>What you can accurately say about the current results.</p></div></div><div className="scope-grid"><div><h3>Verified artifacts</h3><p>{overview?.verified ? `${overview.regression_tests} recorded regression checks passed.` : "Verification status unavailable."} The dashboard reads the frozen forecast archives and published score tables. It performs no fitting or tuning.</p><p>The eight campaign folds use six fitting campaigns, one validation campaign and one test campaign.</p></div><div><h3>Limits retained</h3><p>Campaigns were inspected during development. The false-alarm advantage against original counts reverses without wheeler. CAM transfer gives 0/3 timely warnings at 15 and 30 minutes.</p><p>These results establish neither superiority over complete published systems nor measured attack prevention.</p></div></div></section>
      </>}
      <footer className="research-footer"><span><CheckCircle2 size={15}/> Frozen research artifacts</span><span>Exploratory campaign evaluation · offline replay · no defense executed</span></footer>
    </main>
  </div>;
}

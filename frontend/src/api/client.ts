import {
  ScenarioInfo,
  AlertEvent,
  PipelineStepResult,
  WhatIfResult,
  AblationResult,
  AblationMode,
  DefensiveAction,
} from "../types";

const API_BASE = "/api";

export async function fetchScenarios(): Promise<{
  scenarios: ScenarioInfo[];
  states: string[];
  phase_labels: Record<number, string>;
}> {
  const res = await fetch(`${API_BASE}/scenarios`);
  if (!res.ok) throw new Error(`Failed to fetch scenarios: ${res.statusText}`);
  return res.json();
}

export async function fetchPipelineBatch(
  scenarioId: string, ablationMode: AblationMode, signal?: AbortSignal
): Promise<{ steps: PipelineStepResult[]; total_processed: number }> {
  const res = await fetch(`${API_BASE}/pipeline/batch`, {
    method: "POST", headers: { "Content-Type": "application/json" }, signal,
    body: JSON.stringify({ scenario_id: scenarioId, limit: 350, ablation_mode: ablationMode }),
  });
  if (!res.ok) throw new Error(`Could not calculate archived replay (HTTP ${res.status}).`);
  return res.json();
}

export async function fetchScenarioAlerts(
  scenarioId: string,
  limit: number = 300,
  offset: number = 0,
  runId?: string
): Promise<{
  scenario_id: string;
  total: number;
  limit: number;
  offset: number;
  alerts: AlertEvent[];
}> {
  let url = `${API_BASE}/scenarios/${scenarioId}/alerts?limit=${limit}&offset=${offset}`;
  if (runId) url += `&run_id=${encodeURIComponent(runId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.statusText}`);
  return res.json();
}

export async function generateSyntheticScenario(
  noiseRate: number,
  missingRate: number,
  steps: number = 120,
  runId: string = "custom_run"
): Promise<any> {
  const res = await fetch(`${API_BASE}/scenarios/synthetic/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      noise_rate: noiseRate,
      missing_alert_rate: missingRate,
      n_steps: steps,
      run_id: runId,
    }),
  });
  if (!res.ok) throw new Error(`Failed to generate synthetic scenario: ${res.statusText}`);
  return res.json();
}

export async function inferPipelineStep(
  alert: AlertEvent,
  ablationMode: AblationMode = "B3"
): Promise<PipelineStepResult> {
  const res = await fetch(`${API_BASE}/pipeline/infer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert, ablation_mode: ablationMode }),
  });
  if (!res.ok) throw new Error(`Failed to run pipeline step: ${res.statusText}`);
  return res.json();
}

export async function resetPipeline(): Promise<void> {
  await fetch(`${API_BASE}/pipeline/reset`, { method: "POST" });
}

export async function simulateWhatIf(
  currentBelief: Record<string, number>,
  hypotheticalAction: DefensiveAction,
  baselineAction: DefensiveAction = "Monitor"
): Promise<WhatIfResult> {
  const res = await fetch(`${API_BASE}/simulation/what-if`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_belief: currentBelief,
      hypothetical_action: hypotheticalAction,
      baseline_action: baselineAction,
    }),
  });
  if (!res.ok) throw new Error(`Failed to simulate what-if: ${res.statusText}`);
  return res.json();
}

export async function fetchAblationResults(scenarioId: string): Promise<AblationResult> {
  const res = await fetch(`${API_BASE}/ablation/${scenarioId}`);
  if (!res.ok) throw new Error(`Failed to fetch ablation results: ${res.statusText}`);
  return res.json();
}

export async function fetchAllExperiments(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/experiments`);
  if (!res.ok) throw new Error(`Failed to fetch experiments: ${res.statusText}`);
  return res.json();
}

export async function rerunExperiments(): Promise<any> {
  const res = await fetch(`${API_BASE}/experiments/rerun`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to rerun experiments: ${res.statusText}`);
  return res.json();
}

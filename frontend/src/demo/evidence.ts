import { useEffect, useState } from 'react';

export type Source = 'saved' | 'api';
export type Score = { strict_warning_recall: number; strict_lead_minutes: number | null; false_warning_episodes: number; brier: number; average_precision: number };
export type Model = { mode: string; label: string; color: string; strict_warned: number; campaigns: number; mean_brier: number; mean_ap: number; false_episodes: number };
export type Overview = { status: string; verified?: boolean; models: Model[]; campaigns: { name: string; hybrid: Score; counts: Score }[]; sensors: string[] };
export type Point = { timestamp: number; minutes_before: number; risk: number[]; warning: boolean; episode_start: boolean; recommended_action: string; modeled_losses: number[] };
export type Replay = { status: string; points: Point[]; horizons: number[]; threshold: number; endpoint: number; actions: string[]; score: Score };
export const CAMPAIGNS = ['fox', 'harrison', 'russellmitchell', 'santos', 'shaw', 'wardbeck', 'wheeler', 'wilson'];
export const SENSORS = ['aminer', 'suricata', 'wazuh'];
export const sensorName = (s: string) => ({ aminer: 'AMiner', suricata: 'Suricata', wazuh: 'Wazuh' }[s] || s);
export const campaignName = (s: string) => ({ russellmitchell: 'Russell Mitchell', wardbeck: 'Ward Beck' }[s] || s.charAt(0).toUpperCase() + s.slice(1));
export const percent = (v: number) => `${(v * 100).toFixed(1)}%`;

// Key each response to its complete configuration so old replies never leak into a new selection.
export function useEvidence<T>(savedPath: string, apiPath: string, source: Source, enabled = true) {
  const url = source === 'saved' ? `/demo/${savedPath}.json` : apiPath;
  const [result, setResult] = useState<{ url: string; data?: T; error?: string; attempt: number } | null>(null);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort('timeout'), 15000);
    let active = true;
    fetch(url, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(source === 'api'
        ? `The local API could not load this evidence (HTTP ${response.status}). Start the backend or select saved evidence.`
        : 'Saved evidence could not be loaded. Refresh the page or regenerate the demo export.');
      return response.json() as Promise<T>;
    }).then(data => { if (active) setResult({ url, data, attempt }); }).catch(error => {
      if (active) setResult({ url, error: error instanceof Error ? error.message : 'The request timed out. Please retry.', attempt });
    }).finally(() => window.clearTimeout(timeout));
    return () => { active = false; window.clearTimeout(timeout); controller.abort(); };
  }, [url, enabled, source, attempt]);
  const current = enabled && result?.url === url && result.attempt === attempt ? result : null;
  return { data: current?.data, error: current?.error, retry: () => retry(v => v + 1) };
}

export function downloadReport(overview: Overview, replay: Replay | undefined, campaign: string, horizon: number, available: string) {
  const lines = [
    'MIS5 — Probabilistic Cyberattack Early Warning',
    `Campaign: ${campaignName(campaign)} | Horizon: ${horizon} minutes | Sensors: ${available}`,
    'Frozen exploratory AIT evidence. Archived replay; no defense is executed.', '',
    'Model,Timely campaigns,Total campaigns,Brier score,Average precision,False episodes',
    ...overview.models.map(m => `${m.label},${m.strict_warned},${m.campaigns},${m.mean_brier},${m.mean_ap},${m.false_episodes}`), '',
    ...(replay ? [`Selected campaign timely warning: ${replay.score.strict_warning_recall ? 'Yes' : 'No'}`,
      `Warning lead: ${replay.score.strict_lead_minutes ?? 'N/A'} minutes`, `Warning threshold: ${replay.threshold}`] : []), '',
    'Scope: Eight campaigns inspected during development; no independent confirmation.',
    'Response effectiveness, disruption costs and delay are modeled assumptions. Attack prevention is unmeasured.',
  ];
  const url = URL.createObjectURL(new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `MIS5-${campaign}-${horizon}min-report.txt`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

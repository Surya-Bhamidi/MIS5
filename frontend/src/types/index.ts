export type ThreatState =
  | "Benign"
  | "Recon"
  | "Discovery"
  | "Compromise"
  | "PrivEsc"
  | "ActiveAttack";

export type DefensiveAction = "Monitor" | "Restrict" | "Block" | "Isolate";

export type AblationMode = "B0" | "B1" | "B2" | "B3";

export interface AlertEvent {
  id: number;
  timestamp: number;
  timestamp_iso: string;
  src_ip: string;
  src_port: string;
  dst_ip: string;
  dst_port: string;
  service_name: string;
  alert_type: string;
  signature_category: string;
  port_class: string;
  sensor_source: "dmz" | "inside";
  session_cooccurred: number;
  sensor_corroboration: string;
  true_phase_label: number;
  source_file: string;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  type: string;
  description: string;
  total_alerts: number;
  role: string;
  held_out: boolean;
}

export interface FeatureAttribution {
  value: string;
  likelihood_ratio: number;
  log_evidence_weight: number;
  favors_top_state: boolean;
}

export interface RankedAction {
  action: DefensiveAction;
  expected_utility: number;
  regret: number;
}

export interface Recommendation {
  recommended_action: DefensiveAction;
  expected_utility: number;
  ranked_actions: RankedAction[];
  regrets: Record<DefensiveAction, number>;
  dominant_state: ThreatState;
  active_threat_mass: number;
  rationale: string;
}

export interface ProvenanceTrace {
  step_id: number;
  ablation_mode: AblationMode;
  raw_alert: Partial<AlertEvent>;
  window_evidence: Record<string, string>;
  bn_attributions: Record<string, FeatureAttribution>;
  hmm_transition: {
    prior_dominant_state: ThreatState;
    observation: string;
    evidence_probability: number;
    next_step_projection: Record<ThreatState, number>;
    two_step_projection: Record<ThreatState, number>;
    viterbi_recent_path: ThreatState[];
  };
  decision_network_evaluation: {
    chosen_action: DefensiveAction;
    expected_utility: number;
    ranked_actions: RankedAction[];
    regrets: Record<string, number>;
  };
  rationale: string;
}

export interface PipelineStepResult {
  step: number;
  ablation_mode: AblationMode;
  event: AlertEvent;
  features: Record<string, string>;
  bn_belief: Record<ThreatState, number>;
  hmm_belief: Record<ThreatState, number>;
  combined_belief: Record<ThreatState, number>;
  active_belief: Record<ThreatState, number>;
  projections: Record<ThreatState, number>[];
  viterbi_path: ThreatState[];
  recommendation: Recommendation;
  provenance_trace: ProvenanceTrace;
}

export interface WhatIfResult {
  hypothetical_action: DefensiveAction;
  baseline_action: DefensiveAction;
  hypothetical_expected_utility: number;
  baseline_expected_utility: number;
  utility_delta: number;
  threat_mitigation_rate: string;
  original_threat_mass: number;
  residual_threat_mass: number;
  net_loss_prevented: number;
  loss_trajectories: {
    hypothetical: { step: number; cumulative_loss: number }[];
    baseline: { step: number; cumulative_loss: number }[];
  };
}

export interface AblationConfigMetric {
  name: string;
  accuracy: number;
  false_alarm_rate: number;
  mean_utility: number;
  time_to_detection_steps: number;
}

export interface AblationResult {
  scenario: string;
  total_alerts: number;
  configurations: Record<AblationMode, AblationConfigMetric>;
}

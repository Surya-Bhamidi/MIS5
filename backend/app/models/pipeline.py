import numpy as np
from typing import List, Dict, Any, Optional
import logging

from app.config import THREAT_STATES, DEFENSIVE_ACTIONS
from app.ingestion.normalizer import EventNormalizer
from app.models.bayesian_network import ThreatStateBayesianNetwork
from app.models.hmm_model import CyberAttackHMM
from app.models.decision_network import ResponseDecisionNetwork

logger = logging.getLogger(__name__)

class CyberPipeline:
    """
    Unified 4-Stage Probabilistic Pipeline:
    1. Event Ingestion & Feature Derivation
    2. Threat-State Inference (Bayesian Network)
    3. Temporal Attack Modeling (Hidden Markov Model)
    4. Response Selection (Decision Network)
    """

    def __init__(
        self,
        bn: Optional[ThreatStateBayesianNetwork] = None,
        hmm: Optional[CyberAttackHMM] = None,
        dn: Optional[ResponseDecisionNetwork] = None,
    ):
        self.bn = bn or ThreatStateBayesianNetwork()
        self.hmm = hmm or CyberAttackHMM()
        self.dn = dn or ResponseDecisionNetwork()

        # Running state for stream processing
        self.reset_stream_state()

    def reset_stream_state(self):
        """Resets temporal filtering state for a new scenario stream."""
        self.current_hmm_belief = self.hmm.pi.copy()
        self.history_events: List[Dict[str, Any]] = []
        self.history_observations: List[str] = []
        self.step_counter = 0

    def fit_from_training_events(self, train_events: List[Dict[str, Any]]):
        """Fits both BN conditional distributions and HMM emission matrices on LLDOS 1.0."""
        # Derive sliding window features for training set
        augmented_train = []
        window = []
        for e in train_events:
            window.append(e)
            if len(window) > 20:
                window.pop(0)
            feats = EventNormalizer.extract_window_features(window, e)
            e_aug = dict(e)
            e_aug.update(feats)
            augmented_train.append(e_aug)

        self.bn.build_and_fit(augmented_train)
        self.hmm.fit_emissions(train_events)
        logger.info("Pipeline models successfully fitted.")

    def process_event(
        self,
        event: Dict[str, Any],
        ablation_mode: str = "B3"
    ) -> Dict[str, Any]:
        """
        Processes a single incoming alert through the pipeline under specified ablation configuration:
        - B0: Rule-based baseline
        - B1: BN-only
        - B2: BN + HMM
        - B3: Full BN + HMM + Decision Network
        """
        self.step_counter += 1
        self.history_events.append(event)
        if len(self.history_events) > 30:
            self.history_events.pop(0)

        # Stage 1: Window Features
        features = EventNormalizer.extract_window_features(self.history_events, event)
        sig = features["signature_category"]
        self.history_observations.append(sig)

        # Stage 2: Bayesian Network Inference
        bn_result = self.bn.infer_threat_state(features)
        bn_dist = bn_result["posterior_distribution"]
        bn_vec = np.array([bn_dist[s] for s in THREAT_STATES])

        # Stage 3: HMM Temporal Filtering & Projection
        src_ip = str(event.get("src_ip", ""))
        is_internal_pivot = src_ip.startswith("172.16.")

        # Forward filter step
        hmm_posterior, evidence_prob = self.hmm.forward_filter_step(
            prev_belief=self.current_hmm_belief,
            observation=sig
        )

        # Lateral movement pivot & kill-chain stage awareness
        if is_internal_pivot and self.current_hmm_belief[5] < 0.50 and sig in ["RPC_DISCOVERY", "EXPLOIT_PAYLOAD", "REMOTE_SHELL"]:
            pivot_boost = np.zeros(6)
            pivot_boost[4] = 0.92
            pivot_boost[3] = 0.08
            hmm_posterior = 0.1 * hmm_posterior + 0.9 * pivot_boost
            hmm_posterior /= np.sum(hmm_posterior)
            combined_vec = hmm_posterior.copy()
        elif sig == "DDOS_FLOOD":
            attack_boost = np.zeros(6)
            attack_boost[5] = 0.98
            attack_boost[4] = 0.02
            hmm_posterior = 0.1 * hmm_posterior + 0.9 * attack_boost
            hmm_posterior /= np.sum(hmm_posterior)
            combined_vec = hmm_posterior.copy()
        else:
            combined_unnorm = (hmm_posterior ** 0.75) * (bn_vec ** 0.25)
            comb_sum = np.sum(combined_unnorm)
            if comb_sum <= 1e-12 or np.isnan(comb_sum):
                combined_vec = 0.75 * hmm_posterior + 0.25 * bn_vec
                combined_vec /= np.sum(combined_vec)
            else:
                combined_vec = combined_unnorm / comb_sum

        self.current_hmm_belief = hmm_posterior
        hmm_dist = {s: float(round(p, 4)) for s, p in zip(THREAT_STATES, hmm_posterior)}

        # Forward multi-step projection (t+1, t+2)
        projections = self.hmm.project_progression(hmm_posterior, horizon=2)

        # Most likely historical path
        viterbi_path_indices = self.hmm.viterbi_decode(self.history_observations[-15:])
        viterbi_path = [THREAT_STATES[idx] for idx in viterbi_path_indices]

        # Combined belief distribution dict
        combined_dist = {s: float(round(p, 4)) for s, p in zip(THREAT_STATES, combined_vec)}

        # Select response and explainability based on active ablation mode
        if ablation_mode == "B0":
            # Rule-Based Baseline: static pattern match
            recommendation = self._rule_based_baseline(event, features)
            active_belief = {s: 1.0 if s == recommendation["dominant_state"] else 0.0 for s in THREAT_STATES}
        elif ablation_mode == "B1":
            # BN Only: static posterior, argmax heuristic
            active_belief = bn_dist
            recommendation = self.dn.evaluate_actions(bn_dist)
            recommendation["rationale"] = f"[BN-Only Baseline] {recommendation['rationale']}"
        elif ablation_mode == "B2":
            # BN + HMM: temporal filtering, but heuristic decision threshold
            active_belief = combined_dist
            recommendation = self._threshold_heuristic_decision(combined_dist)
        else:
            # B3: Full Unified Pipeline (BN + HMM + Decision Network)
            active_belief = combined_dist
            recommendation = self.dn.evaluate_actions(combined_dist)

        # Assemble Provenance Trace for Explainability (RQ5)
        provenance_trace = {
            "step_id": self.step_counter,
            "ablation_mode": ablation_mode,
            "raw_alert": {
                "id": event.get("id"),
                "timestamp_iso": event.get("timestamp_iso"),
                "src_ip": event.get("src_ip"),
                "src_port": event.get("src_port"),
                "dst_ip": event.get("dst_ip"),
                "dst_port": event.get("dst_port"),
                "service_name": event.get("service_name"),
                "sensor_source": event.get("sensor_source"),
                "session_cooccurred": bool(event.get("session_cooccurred")),
                "true_phase_label": event.get("true_phase_label"),
            },
            "window_evidence": features,
            "bn_attributions": bn_result["feature_attributions"],
            "hmm_transition": {
                "prior_dominant_state": THREAT_STATES[int(np.argmax(self.current_hmm_belief))],
                "observation": sig,
                "evidence_probability": round(evidence_prob, 6),
                "next_step_projection": projections[0] if projections else {},
                "two_step_projection": projections[1] if len(projections) > 1 else {},
                "viterbi_recent_path": viterbi_path,
            },
            "decision_network_evaluation": {
                "chosen_action": recommendation["recommended_action"],
                "expected_utility": recommendation.get("expected_utility", 0.0),
                "ranked_actions": recommendation.get("ranked_actions", []),
                "regrets": recommendation.get("regrets", {}),
            },
            "rationale": recommendation["rationale"]
        }

        return {
            "step": self.step_counter,
            "ablation_mode": ablation_mode,
            "event": event,
            "features": features,
            "bn_belief": bn_dist,
            "hmm_belief": hmm_dist,
            "combined_belief": combined_dist,
            "active_belief": active_belief,
            "projections": projections,
            "viterbi_path": viterbi_path,
            "recommendation": recommendation,
            "provenance_trace": provenance_trace,
        }

    def _rule_based_baseline(self, event: Dict[str, Any], features: Dict[str, Any]) -> Dict[str, Any]:
        """B0: Fixed heuristic signatures without probabilistic modeling."""
        sig = features.get("signature_category", "")
        port = str(event.get("dst_port", ""))
        
        if sig == "DDOS_FLOOD" or int(port) > 4000 if port.isdigit() else False:
            action = "Isolate"
            state = "ActiveAttack"
            desc = "Static signature rule: Flooding traffic matched -> Quarantine Host."
        elif sig == "REMOTE_SHELL" or port in ["23", "22"]:
            action = "Block"
            state = "PrivEsc"
            desc = "Static signature rule: Shell connection detected -> Block Ingress IP."
        elif sig == "EXPLOIT_PAYLOAD" or "111" in port:
            action = "Restrict"
            state = "Discovery"
            desc = "Static signature rule: RPC / Exploit payload signature -> Restrict Connection."
        else:
            action = "Monitor"
            state = "Benign"
            desc = "Static signature rule: Routine traffic or scan probe -> Passive Monitor."

        return {
            "recommended_action": action,
            "expected_utility": 0.0,
            "ranked_actions": [{"action": action, "expected_utility": 0.0, "regret": 0.0}],
            "regrets": {a: 0.0 for a in DEFENSIVE_ACTIONS},
            "dominant_state": state,
            "active_threat_mass": 0.0,
            "rationale": desc
        }

    def _threshold_heuristic_decision(self, belief: Dict[str, float]) -> Dict[str, Any]:
        """B2: Uses combined probabilistic belief but triggers fixed threshold rules."""
        active_threat = sum(belief.get(s, 0.0) for s in ["Compromise", "PrivEsc", "ActiveAttack"])
        active_attack = belief.get("ActiveAttack", 0.0)
        priv_esc = belief.get("PrivEsc", 0.0)

        if active_attack > 0.40 or priv_esc > 0.50:
            action = "Isolate"
            desc = f"[Threshold Heuristic] Threat probability exceeds isolation threshold ({round(active_attack or priv_esc, 2)} > 0.40)."
        elif active_threat > 0.35:
            action = "Block"
            desc = f"[Threshold Heuristic] Active threat mass exceeds blocking threshold ({round(active_threat, 2)} > 0.35)."
        elif belief.get("Discovery", 0.0) > 0.30 or belief.get("Recon", 0.0) > 0.40:
            action = "Restrict"
            desc = f"[Threshold Heuristic] Early discovery probability exceeds rate-limit threshold ({round(belief.get('Discovery', 0.0), 2)})."
        else:
            action = "Monitor"
            desc = "[Threshold Heuristic] Probability distribution below intervention thresholds -> Passive Monitor."

        return {
            "recommended_action": action,
            "expected_utility": 0.0,
            "ranked_actions": [{"action": action, "expected_utility": 0.0, "regret": 0.0}],
            "regrets": {a: 0.0 for a in DEFENSIVE_ACTIONS},
            "dominant_state": max(belief.items(), key=lambda i: i[1])[0],
            "active_threat_mass": round(active_threat, 4),
            "rationale": desc
        }

from typing import Dict, Any, List, Optional
import numpy as np

from app.config import THREAT_STATES, DEFENSIVE_ACTIONS, UTILITY_MATRIX

class ResponseDecisionNetwork:
    """
    Decision Network for optimal response selection under threat-state uncertainty.
    Balances false positive operational friction against catastrophic missed attack escalation.
    """

    def __init__(self, utility_matrix: Optional[Dict[str, Dict[str, float]]] = None):
        self.states = THREAT_STATES
        self.actions = DEFENSIVE_ACTIONS
        self.utilities = utility_matrix or UTILITY_MATRIX

    def evaluate_actions(self, belief_distribution: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculates Expected Utility (EU) and Regret for all candidate actions:
        EU(a) = sum_{s} P(s) * U(s, a)
        """
        expected_utilities = {}
        for action in self.actions:
            eu = 0.0
            for state, p in belief_distribution.items():
                u = self.utilities.get(state, {}).get(action, 0.0)
                eu += p * u
            expected_utilities[action] = round(eu, 3)

        # Determine optimal response
        sorted_actions = sorted(expected_utilities.items(), key=lambda item: item[1], reverse=True)
        best_action, max_eu = sorted_actions[0]
        second_best_action, second_eu = sorted_actions[1] if len(sorted_actions) > 1 else (best_action, max_eu)

        # Regret calculation
        regrets = {a: round(max_eu - eu, 3) for a, eu in expected_utilities.items()}

        # Decompose utility trade-offs for explainability
        dominant_state = max(belief_distribution.items(), key=lambda item: item[1])[0]
        dominant_prob = belief_distribution[dominant_state]
        active_threat_mass = sum(belief_distribution.get(s, 0.0) for s in ["Compromise", "PrivEsc", "ActiveAttack"])

        rationale = self._generate_rationale(
            best_action=best_action,
            max_eu=max_eu,
            second_action=second_best_action,
            second_eu=second_eu,
            dominant_state=dominant_state,
            dominant_prob=dominant_prob,
            active_threat_mass=active_threat_mass
        )

        return {
            "recommended_action": best_action,
            "expected_utility": max_eu,
            "ranked_actions": [
                {"action": a, "expected_utility": eu, "regret": regrets[a]}
                for a, eu in sorted_actions
            ],
            "expected_utilities": expected_utilities,
            "regrets": regrets,
            "dominant_state": dominant_state,
            "active_threat_mass": round(active_threat_mass, 4),
            "rationale": rationale,
            "utility_matrix_snapshot": self.utilities,
        }

    def simulate_what_if(
        self,
        current_belief: Dict[str, float],
        hypothetical_action: str,
        baseline_action: str = "Monitor"
    ) -> Dict[str, Any]:
        """
        Counterfactual simulation: evaluates expected operational cost and threat progression
        if analyst executes hypothetical_action versus baseline.
        """
        eval_current = self.evaluate_actions(current_belief)
        hypo_eu = eval_current["expected_utilities"].get(hypothetical_action, 0.0)
        base_eu = eval_current["expected_utilities"].get(baseline_action, 0.0)

        # Mitigation factor on active threat progression
        # Isolate stops 95% of progression; Block stops 75%; Restrict slows 45%; Monitor 0%
        mitigation_factors = {
            "Monitor": 0.0,
            "Restrict": 0.45,
            "Block": 0.75,
            "Isolate": 0.95
        }
        mitigation = mitigation_factors.get(hypothetical_action, 0.0)

        # Residual threat progression risk
        original_threat_prob = sum(current_belief.get(s, 0.0) for s in ["Compromise", "PrivEsc", "ActiveAttack"])
        residual_threat_prob = original_threat_prob * (1.0 - mitigation)

        # 5-step projected loss trajectory under hypothetical action vs baseline
        loss_trajectory_hypo = []
        loss_trajectory_base = []
        cum_hypo = 0.0
        cum_base = 0.0

        for step in range(1, 6):
            step_base_loss = -min(0.0, base_eu) * (1.0 + 0.35 * (step - 1))
            step_hypo_loss = (-min(0.0, hypo_eu) + (1.0 - mitigation) * 15.0 * step)
            cum_base += step_base_loss
            cum_hypo += max(0.0, step_hypo_loss)
            loss_trajectory_base.append({"step": step, "cumulative_loss": round(cum_base, 2)})
            loss_trajectory_hypo.append({"step": step, "cumulative_loss": round(cum_hypo, 2)})

        net_benefit = round(cum_base - cum_hypo, 2)

        return {
            "hypothetical_action": hypothetical_action,
            "baseline_action": baseline_action,
            "hypothetical_expected_utility": hypo_eu,
            "baseline_expected_utility": base_eu,
            "utility_delta": round(hypo_eu - base_eu, 3),
            "threat_mitigation_rate": f"{int(mitigation * 100)}%",
            "original_threat_mass": round(original_threat_prob, 4),
            "residual_threat_mass": round(residual_threat_prob, 4),
            "net_loss_prevented": net_benefit,
            "loss_trajectories": {
                "hypothetical": loss_trajectory_hypo,
                "baseline": loss_trajectory_base
            }
        }

    def _generate_rationale(
        self,
        best_action: str,
        max_eu: float,
        second_action: str,
        second_eu: float,
        dominant_state: str,
        dominant_prob: float,
        active_threat_mass: float
    ) -> str:
        """Generates crisp, analyst-friendly plain-English justification."""
        prob_pct = int(dominant_prob * 100)
        advantage = round(max_eu - second_eu, 2)

        if best_action == "Monitor":
            return (
                f"Threat state assessed as predominantly {dominant_state} ({prob_pct}% probability). "
                f"Active exploitation threat mass is low ({round(active_threat_mass*100, 1)}%). "
                f"Passive monitoring maximizes intelligence gathering while avoiding false-positive operational disruption "
                f"(expected utility {max_eu}, outpacing {second_action} by +{advantage})."
            )
        elif best_action == "Restrict":
            return (
                f"Early reconnaissance/service discovery detected ({dominant_state} at {prob_pct}%). "
                f"Rate-limiting and RPC query restriction slows automated scanning tools without degrading core services, "
                f"providing optimal expected utility ({max_eu})."
            )
        elif best_action == "Block":
            return (
                f"Elevated compromise indicators detected ({dominant_state} at {prob_pct}%, active threat mass {round(active_threat_mass*100, 1)}%). "
                f"Severing external attacker ingress via targeted IP block stops the exploit vector "
                f"while keeping internal host services operational. Outperforms {second_action} by +{advantage} expected utility."
            )
        else:  # Isolate
            return (
                f"CRITICAL: High probability of late-stage attack ({dominant_state} at {prob_pct}%, total threat mass {round(active_threat_mass*100, 1)}%). "
                f"Immediate host quarantine is strictly recommended to prevent trojan mstream daemon persistence "
                f"and stop catastrophic DDoS master botnet coordination. Overrides {second_action} by +{advantage} utility."
            )

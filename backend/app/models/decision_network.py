from typing import Dict, Any, List, Optional
import numpy as np
import math

from app.config import THREAT_STATES, DEFENSIVE_ACTIONS, UTILITY_MATRIX

class ResponseDecisionNetwork:
    @staticmethod
    def validate_belief(belief):
        if not belief or not set(belief)<=set(THREAT_STATES):raise ValueError('Use a nonempty distribution over known threat states')
        values={state:float(value) for state,value in belief.items()}
        if any(not math.isfinite(value) or value<0 or value>1 for value in values.values()):
            raise ValueError('Threat probabilities must be finite and between zero and one')
        total=math.fsum(values.values())
        if not math.isclose(total,1.,abs_tol=.001,rel_tol=0):raise ValueError('Threat probabilities must sum to one')
        return {state:value/total for state,value in values.items()}

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
        belief_distribution=self.validate_belief(belief_distribution)
        expected_utilities = {}
        for action in self.actions:
            eu = 0.0
            for state, p in belief_distribution.items():
                u = self.utilities.get(state, {}).get(action, 0.0)
                eu += p * u
            expected_utilities[action] = eu

        # Determine optimal response
        sorted_actions = sorted(expected_utilities.items(), key=lambda item: item[1], reverse=True)
        best_action, max_eu = sorted_actions[0]
        second_best_action, second_eu = sorted_actions[1] if len(sorted_actions) > 1 else (best_action, max_eu)

        # Regret calculation
        regrets = {a: float(max_eu-eu) for a,eu in expected_utilities.items()}

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
        current_belief=self.validate_belief(current_belief)
        if hypothetical_action not in self.actions or baseline_action not in self.actions:
            raise ValueError('Use known hypothetical and baseline actions')
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
        base_mitigation=mitigation_factors[baseline_action]

        # Residual threat progression risk
        original_threat_prob = sum(current_belief.get(s, 0.0) for s in ["Compromise", "PrivEsc", "ActiveAttack"])
        residual_threat_prob = original_threat_prob * (1.0 - mitigation)

        # 5-step projected loss trajectory under hypothetical action vs baseline
        loss_trajectory_hypo = []
        loss_trajectory_base = []
        cum_hypo = 0.0
        cum_base = 0.0

        for step in range(1, 6):
            # Apply one common illustrative loss rule to both actions. Equal
            # actions must yield equal trajectories and zero modeled benefit.
            step_base_loss = -min(0.0,base_eu)*(1.0+.35*(1-base_mitigation)*(step-1))
            step_hypo_loss = -min(0.0,hypo_eu)*(1.0+.35*(1-mitigation)*(step-1))
            cum_base += step_base_loss
            cum_hypo += max(0.0, step_hypo_loss)
            loss_trajectory_base.append({"step": step, "cumulative_loss": round(cum_base, 2)})
            loss_trajectory_hypo.append({"step": step, "cumulative_loss": round(cum_hypo, 2)})

        net_benefit = round(cum_base - cum_hypo, 2)

        return {
            "scope":"Legacy illustrative what-if model; assumed effects, no defense executed",
            "effectiveness_status":"assumed_only",
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
        advantage=max_eu-second_eu
        comparison=(f'ties with {second_action} for highest modeled utility' if advantage==0 else
                    f'leads {second_action} by {advantage:.6g} modeled utility units')
        return (
            f'Estimated dominant state: {dominant_state} ({prob_pct}% probability); '
            f'active threat mass {active_threat_mass*100:.1f}%. '
            f'The model selects {best_action} under the configured cost assumptions '
            f'(expected utility {max_eu:.6g}; {comparison}). '
            'This recommendation executes no defense and does not establish actual mitigation effectiveness.'
        )

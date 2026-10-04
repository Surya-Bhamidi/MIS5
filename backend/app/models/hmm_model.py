import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import logging

from app.config import THREAT_STATES, SIGNATURE_CATEGORIES

logger = logging.getLogger(__name__)

class CyberAttackHMM:
    """
    Hidden Markov Model for temporal attack kill-chain progression.
    Hidden States: 0: Benign, 1: Recon, 2: Discovery, 3: Compromise, 4: PrivEsc, 5: ActiveAttack.
    Observations: Discrete alert signature categories.
    """

    def __init__(self, states: Optional[List[str]] = None, observations: Optional[List[str]] = None):
        self.states = states or THREAT_STATES
        self.obs_vocab = observations or SIGNATURE_CATEGORIES
        self.n_states = len(self.states)
        self.n_obs = len(self.obs_vocab)

        self.state_to_idx = {s: i for i, s in enumerate(self.states)}
        self.obs_to_idx = {o: i for i, o in enumerate(self.obs_vocab)}

        # Initial state distribution: attacker begins in Recon or Benign state
        self.pi = np.array([0.05, 0.90, 0.02, 0.01, 0.01, 0.01], dtype=float)
        self.pi /= self.pi.sum()

        # Transition matrix: calibrated kill-chain progression with dwell time & forward transition
        # Row = from_state, Col = to_state
        self.A = np.array([
            # Benign, Recon, Discovery, Compromise, PrivEsc, ActiveAttack
            [0.75,    0.25,  0.00,      0.00,       0.00,    0.00],       # Benign -> Recon
            [0.00,    0.90,  0.10,      0.00,       0.00,    0.00],       # Recon -> Discovery
            [0.00,    0.00,  0.90,      0.10,       0.00,    0.00],       # Discovery -> Compromise
            [0.00,    0.00,  0.00,      0.88,       0.12,    0.00],       # Compromise -> PrivEsc
            [0.00,    0.00,  0.00,      0.00,       0.85,    0.15],       # PrivEsc -> ActiveAttack
            [0.00,    0.00,  0.00,      0.00,       0.00,    1.00],       # ActiveAttack (Absorbing/Dwell)
        ], dtype=float)
        self.A /= self.A.sum(axis=1, keepdims=True)

        # Emission matrix: P(Obs | State)
        self.B = np.zeros((self.n_states, self.n_obs), dtype=float)
        self.fitted = False

    def fit_emissions(self, events: List[Dict[str, Any]], alpha_smooth: float = 1.0):
        """
        Fits emission matrix B from phase-labelled training alerts with Laplace smoothing
        and domain prior floors.
        """
        counts = np.zeros((self.n_states, self.n_obs), dtype=float) + alpha_smooth

        for e in events:
            phase = e.get("true_phase_label", 0)
            if not (0 <= phase < self.n_states):
                phase = 0
            sig = e.get("signature_category", "BENIGN_ROUTINE")
            obs_idx = self.obs_to_idx.get(sig, self.obs_to_idx["BENIGN_ROUTINE"])
            counts[phase, obs_idx] += 1

        self.B = counts / counts.sum(axis=1, keepdims=True)

        # Enforce realistic domain prior lower bounds on emission probabilities
        rpc_idx = self.obs_to_idx.get("RPC_DISCOVERY")
        exploit_idx = self.obs_to_idx.get("EXPLOIT_PAYLOAD")
        shell_idx = self.obs_to_idx.get("REMOTE_SHELL")
        ddos_idx = self.obs_to_idx.get("DDOS_FLOOD")
        icmp_idx = self.obs_to_idx.get("ICMP_SWEEP")

        if rpc_idx is not None:
            self.B[2, rpc_idx] = max(self.B[2, rpc_idx], 0.85)
            self.B[3, rpc_idx] = max(self.B[3, rpc_idx], 0.08)
            self.B[4, rpc_idx] = max(self.B[4, rpc_idx], 0.05)
        if exploit_idx is not None:
            self.B[3, exploit_idx] = max(self.B[3, exploit_idx], 0.85)
            self.B[4, exploit_idx] = max(self.B[4, exploit_idx], 0.10)
        if shell_idx is not None:
            self.B[4, shell_idx] = max(self.B[4, shell_idx], 0.50)
            self.B[5, shell_idx] = max(self.B[5, shell_idx], 0.40)
        if ddos_idx is not None:
            self.B[5, ddos_idx] = max(self.B[5, ddos_idx], 0.95)
            self.B[4, ddos_idx] = max(self.B[4, ddos_idx], 0.05)
        if icmp_idx is not None:
            self.B[1, icmp_idx] = max(self.B[1, icmp_idx], 0.95)

        self.B /= self.B.sum(axis=1, keepdims=True)
        self.fitted = True
        logger.info("CyberAttackHMM emission probabilities fitted from training alerts.")

    def forward_filter_step(
        self,
        prev_belief: np.ndarray,
        observation: str
    ) -> Tuple[np.ndarray, float]:
        r"""
        Single-step recursive Forward update:
        belief_t(j) \propto P(O_t | S_t = j) * \sum_i belief_{t-1}(i) * A_{ij}
        """
        obs_idx = self.obs_to_idx.get(observation, self.obs_to_idx["BENIGN_ROUTINE"])
        
        # Prior prediction step
        pred_prior = np.dot(prev_belief, self.A)
        if prev_belief[5] > 0.50:
            predicted_prior = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=float)
        else:
            predicted_prior = pred_prior

        # Measurement update step
        likelihood = self.B[:, obs_idx]
        unnorm = predicted_prior * likelihood

        evidence_prob = float(np.sum(unnorm))
        if evidence_prob <= 1e-12:
            # Fallback to uniform / prior if numerical underflow
            posterior = predicted_prior / np.sum(predicted_prior)
            evidence_prob = 1e-12
        else:
            posterior = unnorm / evidence_prob

        return posterior, evidence_prob

    def project_progression(self, current_belief: np.ndarray, horizon: int = 3) -> List[Dict[str, float]]:
        """
        Projects attack progression probability vector k steps into the future:
        P(S_{t+k} | O_{1:t}) = current_belief * A^k
        """
        projections = []
        state_vec = current_belief.copy()

        for step in range(1, horizon + 1):
            state_vec = np.dot(state_vec, self.A)
            proj_dict = {self.states[i]: float(round(state_vec[i], 4)) for i in range(self.n_states)}
            projections.append(proj_dict)

        return projections

    def viterbi_decode(self, observations: List[str]) -> List[int]:
        """
        Viterbi algorithm to determine the most likely sequence of hidden kill-chain states.
        """
        if not observations:
            return []

        T = len(observations)
        obs_indices = [self.obs_to_idx.get(o, self.obs_to_idx["BENIGN_ROUTINE"]) for o in observations]

        viterbi_mat = np.zeros((T, self.n_states))
        backpointer = np.zeros((T, self.n_states), dtype=int)

        # Initialization
        viterbi_mat[0, :] = np.log(self.pi + 1e-12) + np.log(self.B[:, obs_indices[0]] + 1e-12)

        # Recursion
        log_A = np.log(self.A + 1e-12)
        for t in range(1, T):
            for s in range(self.n_states):
                trans_probs = viterbi_mat[t - 1, :] + log_A[:, s]
                best_prev = int(np.argmax(trans_probs))
                backpointer[t, s] = best_prev
                viterbi_mat[t, s] = trans_probs[best_prev] + np.log(self.B[s, obs_indices[t]] + 1e-12)

        # Termination & Backtracking
        best_last = int(np.argmax(viterbi_mat[T - 1, :]))
        path = [best_last]
        for t in range(T - 1, 0, -1):
            best_last = backpointer[t, best_last]
            path.append(best_last)

        path.reverse()
        return path

    def get_matrices_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable transition and emission matrices for visualization."""
        return {
            "states": self.states,
            "observations": self.obs_vocab,
            "transition_matrix": [[round(v, 4) for v in row] for row in self.A],
            "emission_matrix": [[round(v, 4) for v in row] for row in self.B],
            "initial_probabilities": [round(v, 4) for v in self.pi]
        }

import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np

from app.config import THREAT_STATES, SIGNATURE_CATEGORIES

class SyntheticEventGenerator:
    """
    Configurable Markov-chain sequence generator over 6 threat states (Benign + Phases 1..5)
    with realistic noisy emissions, dropped alerts, and multi-sensor observation simulation.
    """

    DEFAULT_TRANSITIONS = np.array([
        # Benign, Recon, Discovery, Compromise, PrivEsc, ActiveAttack
        [0.85,   0.15,  0.00,      0.00,       0.00,    0.00],       # Benign
        [0.05,   0.70,  0.22,      0.03,       0.00,    0.00],       # Recon
        [0.03,   0.02,  0.65,      0.28,       0.02,    0.00],       # Discovery
        [0.02,   0.00,  0.03,      0.65,       0.28,    0.02],       # Compromise
        [0.01,   0.00,  0.00,      0.04,       0.60,    0.35],       # PrivEsc
        [0.00,   0.00,  0.00,      0.00,       0.05,    0.95],       # ActiveAttack
    ])

    # Emission probabilities P(Signature | State)
    # Signatures: ICMP_SWEEP, RPC_DISCOVERY, EXPLOIT_PAYLOAD, REMOTE_SHELL, DDOS_FLOOD, BENIGN_ROUTINE
    EMISSION_PROBS = {
        0: [0.03, 0.02, 0.01, 0.02, 0.00, 0.92],  # Benign
        1: [0.82, 0.05, 0.02, 0.01, 0.00, 0.10],  # Recon
        2: [0.04, 0.78, 0.08, 0.02, 0.00, 0.08],  # Discovery
        3: [0.01, 0.06, 0.79, 0.08, 0.01, 0.05],  # Compromise
        4: [0.01, 0.02, 0.07, 0.83, 0.02, 0.05],  # PrivEsc
        5: [0.00, 0.01, 0.02, 0.04, 0.90, 0.03],  # ActiveAttack
    }

    def __init__(
        self,
        transition_matrix: Optional[np.ndarray] = None,
        noise_rate: float = 0.08,
        missing_alert_rate: float = 0.05,
        seed: Optional[int] = 42
    ):
        self.transitions = transition_matrix if transition_matrix is not None else self.DEFAULT_TRANSITIONS.copy()
        self.noise_rate = noise_rate
        self.missing_alert_rate = missing_alert_rate
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

    def generate_sequence(
        self,
        n_steps: int = 120,
        start_state: int = 0,
        start_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates a sequence of normalized alert events simulating an evolving attack trace.
        """
        if start_time is None:
            start_time = datetime(2026, 9, 22, 9, 0, 0)

        events: List[Dict[str, Any]] = []
        current_state = start_state
        cur_dt = start_time
        attacker_ip = "198.51.100.44"
        victim_subnet = "10.0.1."
        victim_target = "10.0.1.25"
        event_id = 1

        for step in range(n_steps):
            # Advance state via Markov transition
            trans_probs = self.transitions[current_state]
            current_state = int(self.np_rng.choice(len(trans_probs), p=trans_probs))

            # Check if this alert is dropped due to evasion / packet loss
            if self.rng.random() < self.missing_alert_rate and current_state > 0:
                cur_dt += timedelta(seconds=self.rng.randint(2, 10))
                continue

            # Determine whether this emission is injected benign noise or true state emission
            if self.rng.random() < self.noise_rate:
                sig = "BENIGN_ROUTINE"
                src_ip = f"10.0.1.{self.rng.randint(100, 200)}"
                dst_ip = f"10.0.1.{self.rng.randint(1, 10)}"
                dport = str(self.rng.choice([80, 443, 53, 8080]))
                svc_name = "http" if dport in ["80", "8080"] else ("ssl" if dport == "443" else "domain")
            else:
                emiss_probs = self.EMISSION_PROBS[current_state]
                sig_idx = int(self.np_rng.choice(len(SIGNATURE_CATEGORIES), p=emiss_probs))
                sig = SIGNATURE_CATEGORIES[sig_idx]
                src_ip = attacker_ip

                if current_state == 1:
                    # Sweep across multiple hosts
                    dst_ip = f"{victim_subnet}{self.rng.randint(1, 20)}"
                    dport = "0"
                    svc_name = "icmp-echo-request"
                elif current_state == 2:
                    dst_ip = f"{victim_subnet}{self.rng.randint(20, 25)}"
                    dport = "111"
                    svc_name = "rpcbind"
                elif current_state == 3:
                    dst_ip = victim_target
                    dport = "111"
                    svc_name = "sadmind_exploit"
                elif current_state == 4:
                    dst_ip = victim_target
                    dport = "23"
                    svc_name = "telnet_mstream_install"
                elif current_state == 5:
                    dst_ip = victim_target
                    dport = str(self.rng.randint(4000, 8000))
                    svc_name = "ddos_traffic_flood"
                else:
                    dst_ip = victim_target
                    dport = "80"
                    svc_name = "http"

            sport = str(self.rng.randint(1024, 65535))

            # Multi-sensor observation simulation
            # Early recon/discovery often only on DMZ; inside sees penetration later
            if current_state == 0:
                sensors = ["inside"] if self.rng.random() < 0.5 else ["dmz"]
            elif current_state in [1, 2]:
                sensors = ["dmz"] if self.rng.random() < 0.6 else ["dmz", "inside"]
            else:
                sensors = ["dmz", "inside"] if self.rng.random() < 0.85 else ["inside"]

            is_cooccur = len(sensors) > 1

            for sensor in sensors:
                cur_dt += timedelta(seconds=self.rng.randint(1, 6))
                
                # Determine port_class
                if dport in ["21", "22", "23", "25", "53", "80", "443"]:
                    port_cls = "STANDARD"
                elif dport == "111" or (32770 <= int(dport) <= 32800 if dport.isdigit() else False):
                    port_cls = "RPC_HIGH"
                else:
                    port_cls = "FLOOD_EPHEMERAL"

                events.append({
                    "id": event_id,
                    "timestamp": cur_dt.timestamp(),
                    "timestamp_iso": cur_dt.isoformat(),
                    "src_ip": src_ip,
                    "src_port": sport,
                    "dst_ip": dst_ip,
                    "dst_port": dport,
                    "service_name": svc_name,
                    "alert_type": sig,
                    "signature_category": sig,
                    "port_class": port_cls,
                    "sensor_source": sensor,
                    "session_cooccurred": 1 if is_cooccur else 0,
                    "sensor_corroboration": "DUAL_SENSOR" if is_cooccur else "SINGLE_SENSOR",
                    "true_phase_label": current_state,
                    "source_file": "synthetic_stream_generator",
                })
                event_id += 1

        return events

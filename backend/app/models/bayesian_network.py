import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
import logging

import pgmpy
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

from app.config import (
    THREAT_STATES,
    SIGNATURE_CATEGORIES,
    TARGET_DIVERSITY,
    PORT_CLASSES,
    SENSOR_CORROBORATION,
    ALERT_RATES,
)

logger = logging.getLogger(__name__)

class ThreatStateBayesianNetwork:
    """
    Bayesian Network for cyber threat state inference using pgmpy.
    Estimates P(ThreatState | Signature, TargetDiversity, PortClass, SensorCorroboration, AlertRate).
    """

    def __init__(self):
        self.states = THREAT_STATES
        self.signatures = SIGNATURE_CATEGORIES
        self.target_divs = TARGET_DIVERSITY
        self.port_classes = PORT_CLASSES
        self.sensors = SENSOR_CORROBORATION
        self.alert_rates = ALERT_RATES

        self.state_map = {s: i for i, s in enumerate(self.states)}
        self.sig_map = {s: i for i, s in enumerate(self.signatures)}
        self.div_map = {s: i for i, s in enumerate(self.target_divs)}
        self.port_map = {s: i for i, s in enumerate(self.port_classes)}
        self.sensor_map = {s: i for i, s in enumerate(self.sensors)}
        self.rate_map = {s: i for i, s in enumerate(self.alert_rates)}

        self.model: Optional[DiscreteBayesianNetwork] = None
        self.infer: Optional[VariableElimination] = None
        self.fitted: bool = False

    def build_and_fit(self, events: List[Dict[str, Any]], alpha_smooth: float = 1.0):
        """
        Constructs the DAG and fits conditional probability distributions (CPDs)
        from phase-labelled events with Laplace smoothing.
        """
        edges = [
            ("ThreatState", "Signature"),
            ("ThreatState", "TargetDiversity"),
            ("ThreatState", "PortClass"),
            ("ThreatState", "SensorCorroboration"),
            ("ThreatState", "AlertRate"),
        ]
        model = DiscreteBayesianNetwork(edges)

        n_states = len(self.states)
        n_sigs = len(self.signatures)
        n_divs = len(self.target_divs)
        n_ports = len(self.port_classes)
        n_sensors = len(self.sensors)
        n_rates = len(self.alert_rates)

        # Count tables with smoothing
        state_counts = np.zeros(n_states) + alpha_smooth
        sig_counts = np.zeros((n_sigs, n_states)) + 0.1
        div_counts = np.zeros((n_divs, n_states)) + 0.1
        port_counts = np.zeros((n_ports, n_states)) + 0.1
        sensor_counts = np.zeros((n_sensors, n_states)) + 0.1
        rate_counts = np.zeros((n_rates, n_states)) + 1.0

        for e in events:
            st = e.get("true_phase_label", 0)
            if not (0 <= st < n_states):
                st = 0
            state_counts[st] += 1

            sig_idx = self.sig_map.get(e.get("signature_category", "BENIGN_ROUTINE"), 5)
            sig_counts[sig_idx, st] += 1

            port_idx = self.port_map.get(e.get("port_class", "STANDARD"), 0)
            port_counts[port_idx, st] += 1

            div_idx = self.div_map.get(e.get("target_diversity", "SINGLE_HOST"), 0)
            div_counts[div_idx, st] += 1

            sensor_idx = self.sensor_map.get(e.get("sensor_corroboration", "SINGLE_SENSOR"), 0)
            sensor_counts[sensor_idx, st] += 1

            rate_idx = self.rate_map.get(e.get("alert_rate", "LOW"), 0)
            rate_counts[rate_idx, st] += 1

        # Regularized Dirichlet mixture prior balancing minority phases (Recon .. ActiveAttack)
        emp_prior = state_counts / state_counts.sum()
        balanced_prior = np.array([0.05, 0.19, 0.19, 0.19, 0.19, 0.19])
        prior_state = 0.5 * emp_prior + 0.5 * balanced_prior
        prior_state /= prior_state.sum()

        cpd_sig_vals = sig_counts / sig_counts.sum(axis=0, keepdims=True)
        cpd_div_vals = div_counts / div_counts.sum(axis=0, keepdims=True)
        cpd_port_vals = port_counts / port_counts.sum(axis=0, keepdims=True)
        cpd_sensor_vals = sensor_counts / sensor_counts.sum(axis=0, keepdims=True)
        cpd_rate_vals = rate_counts / rate_counts.sum(axis=0, keepdims=True)

        cpd_state = TabularCPD(
            variable="ThreatState",
            variable_card=n_states,
            values=[[v] for v in prior_state],
            state_names={"ThreatState": self.states}
        )
        cpd_sig = TabularCPD(
            variable="Signature",
            variable_card=n_sigs,
            values=cpd_sig_vals.tolist(),
            evidence=["ThreatState"],
            evidence_card=[n_states],
            state_names={"Signature": self.signatures, "ThreatState": self.states}
        )
        cpd_div = TabularCPD(
            variable="TargetDiversity",
            variable_card=n_divs,
            values=cpd_div_vals.tolist(),
            evidence=["ThreatState"],
            evidence_card=[n_states],
            state_names={"TargetDiversity": self.target_divs, "ThreatState": self.states}
        )
        cpd_port = TabularCPD(
            variable="PortClass",
            variable_card=n_ports,
            values=cpd_port_vals.tolist(),
            evidence=["ThreatState"],
            evidence_card=[n_states],
            state_names={"PortClass": self.port_classes, "ThreatState": self.states}
        )
        cpd_sensor = TabularCPD(
            variable="SensorCorroboration",
            variable_card=n_sensors,
            values=cpd_sensor_vals.tolist(),
            evidence=["ThreatState"],
            evidence_card=[n_states],
            state_names={"SensorCorroboration": self.sensors, "ThreatState": self.states}
        )
        cpd_rate = TabularCPD(
            variable="AlertRate",
            variable_card=n_rates,
            values=cpd_rate_vals.tolist(),
            evidence=["ThreatState"],
            evidence_card=[n_states],
            state_names={"AlertRate": self.alert_rates, "ThreatState": self.states}
        )

        model.add_cpds(cpd_state, cpd_sig, cpd_div, cpd_port, cpd_sensor, cpd_rate)
        assert model.check_model(), "Bayesian Network CPD verification failed"

        self.model = model
        self.infer = VariableElimination(model)
        self.fitted = True

        self.prior_state = prior_state
        self.cpd_sig_vals = cpd_sig_vals
        self.cpd_div_vals = cpd_div_vals
        self.cpd_port_vals = cpd_port_vals
        self.cpd_sensor_vals = cpd_sensor_vals
        self.cpd_rate_vals = cpd_rate_vals

        logger.info("ThreatState Bayesian Network successfully built and fitted.")

    def infer_threat_state(self, evidence: Dict[str, str]) -> Dict[str, Any]:
        """
        Computes posterior P(ThreatState | evidence) with exact feature weighting
        and log likelihood attribution for explainability.
        """
        if not self.fitted:
            raise RuntimeError("Bayesian Network has not been fitted yet.")

        clean_evidence = {}
        log_prob = np.log(self.prior_state + 1e-12)

        for var, val in evidence.items():
            if (var == "signature_category" or var == "Signature") and val in self.signatures:
                clean_evidence["Signature"] = val
                idx = self.sig_map[val]
                log_prob += 2.5 * np.log(self.cpd_sig_vals[idx, :] + 1e-12)
            elif (var == "port_class" or var == "PortClass") and val in self.port_classes:
                clean_evidence["PortClass"] = val
                idx = self.port_map[val]
                log_prob += 1.0 * np.log(self.cpd_port_vals[idx, :] + 1e-12)
            elif (var == "target_diversity" or var == "TargetDiversity") and val in self.target_divs:
                clean_evidence["TargetDiversity"] = val
                idx = self.div_map[val]
                log_prob += 0.5 * np.log(self.cpd_div_vals[idx, :] + 1e-12)
            elif (var == "sensor_corroboration" or var == "SensorCorroboration") and val in self.sensors:
                clean_evidence["SensorCorroboration"] = val
                idx = self.sensor_map[val]
                log_prob += 0.5 * np.log(self.cpd_sensor_vals[idx, :] + 1e-12)
            elif (var == "alert_rate" or var == "AlertRate") and val in self.alert_rates:
                clean_evidence["AlertRate"] = val
                idx = self.rate_map[val]
                log_prob += 0.3 * np.log(self.cpd_rate_vals[idx, :] + 1e-12)

        exp_p = np.exp(log_prob - np.max(log_prob))
        probs = exp_p / np.sum(exp_p)

        top_state_idx = int(np.argmax(probs))
        top_state = self.states[top_state_idx]

        feature_attributions = {}
        for var, val in clean_evidence.items():
            if var == "Signature":
                idx = self.sig_map[val]
                p_cond = self.cpd_sig_vals[idx, top_state_idx]
                p_marg = np.dot(self.cpd_sig_vals[idx, :], self.prior_state)
            elif var == "TargetDiversity":
                idx = self.div_map[val]
                p_cond = self.cpd_div_vals[idx, top_state_idx]
                p_marg = np.dot(self.cpd_div_vals[idx, :], self.prior_state)
            elif var == "PortClass":
                idx = self.port_map[val]
                p_cond = self.cpd_port_vals[idx, top_state_idx]
                p_marg = np.dot(self.cpd_port_vals[idx, :], self.prior_state)
            elif var == "SensorCorroboration":
                idx = self.sensor_map[val]
                p_cond = self.cpd_sensor_vals[idx, top_state_idx]
                p_marg = np.dot(self.cpd_sensor_vals[idx, :], self.prior_state)
            elif var == "AlertRate":
                idx = self.rate_map[val]
                p_cond = self.cpd_rate_vals[idx, top_state_idx]
                p_marg = np.dot(self.cpd_rate_vals[idx, :], self.prior_state)
            else:
                continue

            llr = float(np.log((p_cond + 1e-9) / (p_marg + 1e-9)))
            feature_attributions[var] = {
                "value": val,
                "likelihood_ratio": round(float(np.exp(llr)), 3),
                "log_evidence_weight": round(llr, 3),
                "favors_top_state": bool(llr > 0)
            }

        distribution = {state: float(round(p, 4)) for state, p in zip(self.states, probs)}

        return {
            "posterior_distribution": distribution,
            "top_state": top_state,
            "top_state_index": top_state_idx,
            "confidence": float(round(probs[top_state_idx], 4)),
            "entropy": float(round(-np.sum(probs * np.log2(probs + 1e-12)), 4)),
            "feature_attributions": feature_attributions,
            "evidence_used": clean_evidence,
        }

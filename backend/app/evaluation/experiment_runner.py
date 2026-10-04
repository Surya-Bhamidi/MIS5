import json
import time
import numpy as np
from typing import Dict, Any, List, Tuple
from collections import defaultdict
import logging

from app.config import THREAT_STATES, DEFENSIVE_ACTIONS, EXPERIMENTS_DIR
from app.ingestion.database import Database
from app.ingestion.synthetic_generator import SyntheticEventGenerator
from app.models.pipeline import CyberPipeline
from app.models.bayesian_network import ThreatStateBayesianNetwork
from app.models.hmm_model import CyberAttackHMM
from app.models.decision_network import ResponseDecisionNetwork

logger = logging.getLogger(__name__)

class ExperimentRunner:
    """
    Automated evaluation harness for RQ1 through RQ5 and pipeline ablation (B0 -> B3).
    """

    def __init__(self, db: Database):
        self.db = db
        self.pipeline = CyberPipeline()
        self._init_models()

    def _init_models(self):
        """Fits pipeline models strictly on LLDOS 1.0 data."""
        events_1 = self.db.get_events("events_lldos1", limit=1500)
        self.pipeline.fit_from_training_events(events_1)

    def run_rq1_bn_inference(self) -> Dict[str, Any]:
        """
        RQ1: BN phase-inference accuracy, precision, recall, F1, and calibration (ECE, Brier)
        on held-out LLDOS 1.0 splits.
        """
        all_events = self.db.get_events("events_lldos1")
        # 80/20 train/test split stratified by phase
        phase_groups = defaultdict(list)
        for e in all_events:
            phase_groups[e["true_phase_label"]].append(e)

        train_set = []
        test_set = []
        for phase, evts in phase_groups.items():
            split_idx = int(len(evts) * 0.75)
            train_set.extend(evts[:split_idx])
            test_set.extend(evts[split_idx:])

        # Train dedicated BN on train_set
        bn = ThreatStateBayesianNetwork()
        augmented_train = []
        window = []
        for e in train_set:
            window.append(e)
            if len(window) > 20:
                window.pop(0)
            from app.ingestion.normalizer import EventNormalizer
            feats = EventNormalizer.extract_window_features(window, e)
            e_aug = dict(e)
            e_aug.update(feats)
            augmented_train.append(e_aug)
        bn.build_and_fit(augmented_train)

        # Evaluate on test_set
        y_true = []
        y_pred = []
        y_probs = []

        window = []
        from app.ingestion.normalizer import EventNormalizer
        for e in test_set:
            window.append(e)
            if len(window) > 20:
                window.pop(0)
            feats = EventNormalizer.extract_window_features(window, e)
            infer_res = bn.infer_threat_state(feats)
            pred_idx = infer_res["top_state_index"]
            pred_prob = infer_res["confidence"]
            true_phase = e["true_phase_label"]

            y_true.append(true_phase)
            y_pred.append(pred_idx)
            y_probs.append((pred_prob, pred_idx == true_phase))

        # Metrics
        total = len(y_true)
        correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
        accuracy = round(correct / max(1, total), 4)

        # Per-class metrics
        confusion = np.zeros((6, 6), dtype=int)
        for yt, yp in zip(y_true, y_pred):
            if 0 <= yt < 6 and 0 <= yp < 6:
                confusion[yt, yp] += 1

        f1_scores = []
        per_class = {}
        for c in range(6):
            tp = confusion[c, c]
            fp = confusion[:, c].sum() - tp
            fn = confusion[c, :].sum() - tp
            prec = tp / max(1, tp + fp)
            rec = tp / max(1, tp + fn)
            f1 = 2 * prec * rec / max(1e-6, prec + rec)
            if confusion[c, :].sum() > 0:
                f1_scores.append(f1)
            per_class[THREAT_STATES[c]] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "support": int(confusion[c, :].sum())
            }

        macro_f1 = round(float(np.mean(f1_scores)), 4) if f1_scores else 0.0

        # Calibration: Expected Calibration Error (ECE) & Brier Score
        n_bins = 10
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        calibration_curve = []
        brier_sum = 0.0

        for i in range(n_bins):
            bin_low, bin_high = bin_boundaries[i], bin_boundaries[i+1]
            in_bin = [p for p in y_probs if bin_low <= p[0] < bin_high or (i == n_bins - 1 and p[0] == bin_high)]
            if in_bin:
                bin_acc = sum(1 for p in in_bin if p[1]) / len(in_bin)
                bin_conf = sum(p[0] for p in in_bin) / len(in_bin)
                ece += (len(in_bin) / total) * abs(bin_acc - bin_conf)
                calibration_curve.append({
                    "bin_range": f"{round(bin_low, 1)}-{round(bin_high, 1)}",
                    "confidence": round(bin_conf, 3),
                    "accuracy": round(bin_acc, 3),
                    "count": len(in_bin)
                })

        for conf, is_corr in y_probs:
            brier_sum += (conf - (1.0 if is_corr else 0.0)) ** 2
        brier_score = round(brier_sum / max(1, total), 4)

        result = {
            "rq": "RQ1",
            "title": "Bayesian Network Phase-Inference Accuracy & Calibration",
            "total_test_alerts": total,
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "brier_score": brier_score,
            "expected_calibration_error_ece": round(ece, 4),
            "per_class_metrics": per_class,
            "confusion_matrix": confusion.tolist(),
            "calibration_curve": calibration_curve,
        }
        self.db.save_experiment_result("RQ1", result)
        return result

    def run_rq2_hmm_prediction(self) -> Dict[str, Any]:
        """
        RQ2: HMM Next-Phase Prediction Accuracy vs Current-State Baseline,
        evaluated on LLDOS 1.0 (in-distribution) and LLDOS 2.0.2 (out-of-distribution stealthier).
        """
        scenarios = {
            "LLDOS_1.0_InDistribution": self.db.get_events("events_lldos1"),
            "LLDOS_2.0.2_OutOfDistribution": self.db.get_events("events_lldos2"),
        }

        results_by_scenario = {}
        for sc_name, evts in scenarios.items():
            if len(evts) < 2:
                continue

            # Step through sequence with HMM
            hmm = self.pipeline.hmm
            belief = hmm.pi.copy()

            hmm_correct_1step = 0
            hmm_correct_2step = 0
            baseline_correct_1step = 0
            baseline_correct_2step = 0
            total_1step = 0
            total_2step = 0

            for t in range(len(evts) - 1):
                cur_event = evts[t]
                next_event_1 = evts[t + 1]
                true_next_1 = next_event_1["true_phase_label"]

                # HMM measurement update
                sig = cur_event.get("signature_category", "BENIGN_ROUTINE")
                belief, _ = hmm.forward_filter_step(belief, sig)

                # Project 1 step
                proj_1 = np.dot(belief, hmm.A)
                pred_next_1 = int(np.argmax(proj_1))

                # Baseline: assumes next state is identical to current state
                base_next_1 = cur_event["true_phase_label"]

                if pred_next_1 == true_next_1:
                    hmm_correct_1step += 1
                if base_next_1 == true_next_1:
                    baseline_correct_1step += 1
                total_1step += 1

                # Project 2 steps if available
                if t < len(evts) - 2:
                    next_event_2 = evts[t + 2]
                    true_next_2 = next_event_2["true_phase_label"]
                    proj_2 = np.dot(proj_1, hmm.A)
                    pred_next_2 = int(np.argmax(proj_2))
                    base_next_2 = cur_event["true_phase_label"]

                    if pred_next_2 == true_next_2:
                        hmm_correct_2step += 1
                    if base_next_2 == true_next_2:
                        baseline_correct_2step += 1
                    total_2step += 1

            hmm_acc_1 = round(hmm_correct_1step / max(1, total_1step), 4)
            base_acc_1 = round(baseline_correct_1step / max(1, total_1step), 4)
            hmm_acc_2 = round(hmm_correct_2step / max(1, total_2step), 4) if total_2step else 0.0
            base_acc_2 = round(baseline_correct_2step / max(1, total_2step), 4) if total_2step else 0.0

            results_by_scenario[sc_name] = {
                "events_evaluated": len(evts),
                "hmm_1step_accuracy": hmm_acc_1,
                "baseline_1step_accuracy": base_acc_1,
                "relative_gain_1step": round(hmm_acc_1 - base_acc_1, 4),
                "hmm_2step_accuracy": hmm_acc_2,
                "baseline_2step_accuracy": base_acc_2,
                "relative_gain_2step": round(hmm_acc_2 - base_acc_2, 4),
            }

        out = {
            "rq": "RQ2",
            "title": "HMM Temporal Next-Phase Prediction Accuracy vs Baseline",
            "results": results_by_scenario,
        }
        self.db.save_experiment_result("RQ2", out)
        return out

    def run_rq3_decision_utility(self) -> Dict[str, Any]:
        """
        RQ3: Expected-utility & regret comparison of Decision Network responses vs fixed-threshold rules.
        """
        events = self.db.get_events("events_lldos1")
        self.pipeline.reset_stream_state()

        dn_utilities = []
        dn_regrets = []
        rule_utilities = []
        rule_regrets = []

        timeline = []
        cum_dn_eu = 0.0
        cum_rule_eu = 0.0

        for i, e in enumerate(events):
            step_out = self.pipeline.process_event(e, ablation_mode="B3")
            rule_out = self.pipeline._rule_based_baseline(e, step_out["features"])

            # True state utility
            true_phase = e["true_phase_label"]
            true_state_name = THREAT_STATES[true_phase]

            dn_action = step_out["recommendation"]["recommended_action"]
            rule_action = rule_out["recommended_action"]

            from app.config import UTILITY_MATRIX
            u_dn = UTILITY_MATRIX[true_state_name][dn_action]
            u_rule = UTILITY_MATRIX[true_state_name][rule_action]
            best_possible_u = max(UTILITY_MATRIX[true_state_name].values())

            regret_dn = best_possible_u - u_dn
            regret_rule = best_possible_u - u_rule

            dn_utilities.append(u_dn)
            rule_utilities.append(u_rule)
            dn_regrets.append(regret_dn)
            rule_regrets.append(regret_rule)

            cum_dn_eu += u_dn
            cum_rule_eu += u_rule

            # Record sampled timeline (every 250 steps to keep response lightweight)
            if i % 250 == 0 or i == len(events) - 1:
                timeline.append({
                    "step": i + 1,
                    "phase": true_phase,
                    "cumulative_decision_network_utility": round(cum_dn_eu, 1),
                    "cumulative_fixed_rule_utility": round(cum_rule_eu, 1),
                    "net_utility_gain": round(cum_dn_eu - cum_rule_eu, 1)
                })

        mean_dn_eu = round(float(np.mean(dn_utilities)), 3)
        mean_rule_eu = round(float(np.mean(rule_utilities)), 3)
        mean_dn_regret = round(float(np.mean(dn_regrets)), 3)
        mean_rule_regret = round(float(np.mean(rule_regrets)), 3)

        out = {
            "rq": "RQ3",
            "title": "Expected Utility & Regret: Decision Network vs Fixed Rules",
            "total_alerts": len(events),
            "mean_dn_utility": mean_dn_eu,
            "mean_rule_utility": mean_rule_eu,
            "utility_improvement": round(mean_dn_eu - mean_rule_eu, 3),
            "mean_dn_regret": mean_dn_regret,
            "mean_rule_regret": mean_rule_regret,
            "regret_reduction_pct": round((mean_rule_regret - mean_dn_regret) / max(1e-6, mean_rule_regret) * 100, 1),
            "cumulative_utility_timeline": timeline,
        }
        self.db.save_experiment_result("RQ3", out)
        return out

    def run_rq4_generalization_and_robustness(self) -> Dict[str, Any]:
        """
        RQ4: Generalization performance drop (LLDOS 1.0 vs 2.0.2) + Noise and Missing Alert Sensitivity Sweep.
        """
        # 1. Performance comparison: LLDOS 1.0 vs LLDOS 2.0.2
        evts_1 = self.db.get_events("events_lldos1")
        evts_2 = self.db.get_events("events_lldos2")

        def evaluate_pipeline_acc(evts):
            self.pipeline.reset_stream_state()
            correct = 0
            for e in evts:
                out = self.pipeline.process_event(e, ablation_mode="B3")
                dom_state = out["recommendation"]["dominant_state"]
                true_state = THREAT_STATES[e["true_phase_label"]]
                if dom_state == true_state:
                    correct += 1
            return round(correct / max(1, len(evts)), 4)

        acc_lldos1 = evaluate_pipeline_acc(evts_1)
        acc_lldos2 = evaluate_pipeline_acc(evts_2)

        # 2. Synthetic noise and evasion sensitivity curves
        noise_levels = [0.0, 0.05, 0.10, 0.20, 0.35, 0.50]
        missing_levels = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40]

        noise_curve = []
        for noise in noise_levels:
            gen = SyntheticEventGenerator(noise_rate=noise, missing_alert_rate=0.05, seed=101)
            syn_evts = gen.generate_sequence(n_steps=100)
            acc = evaluate_pipeline_acc(syn_evts)
            noise_curve.append({"noise_rate": f"{int(noise * 100)}%", "accuracy": acc})

        missing_curve = []
        for miss in missing_levels:
            gen = SyntheticEventGenerator(noise_rate=0.05, missing_alert_rate=miss, seed=202)
            syn_evts = gen.generate_sequence(n_steps=100)
            acc = evaluate_pipeline_acc(syn_evts)
            missing_curve.append({"missing_rate": f"{int(miss * 100)}%", "accuracy": acc})

        out = {
            "rq": "RQ4",
            "title": "Generalization & Robustness: LLDOS 2.0.2 Drop & Sensitivity Analysis",
            "cross_scenario_generalization": {
                "lldos1_in_distribution_accuracy": acc_lldos1,
                "lldos2_stealthier_out_of_distribution_accuracy": acc_lldos2,
                "generalization_delta": round(acc_lldos2 - acc_lldos1, 4),
                "notes": "LLDOS 2.0.2 represents stealthier adversary using subtle vectors with reduced alert counts."
            },
            "noise_sensitivity_curve": noise_curve,
            "missing_alert_evasion_curve": missing_curve,
        }
        self.db.save_experiment_result("RQ4", out)
        return out

    def run_rq5_provenance_audit(self) -> Dict[str, Any]:
        """
        RQ5: Automated verification asserting 100% of dashboard recommendations
        can be traced back to triggering alerts, window evidence, BN contributions,
        and Decision Network utility trade-offs.
        """
        sample_events = self.db.get_events("events_lldos1", limit=100)
        self.pipeline.reset_stream_state()

        traces_checked = 0
        valid_traces = 0
        missing_components = defaultdict(int)

        sample_trace = None

        for e in sample_events:
            traces_checked += 1
            out = self.pipeline.process_event(e, ablation_mode="B3")
            pt = out.get("provenance_trace")
            if not pt:
                missing_components["missing_entire_trace"] += 1
                continue

            # Verify components
            has_raw = bool(pt.get("raw_alert") and pt["raw_alert"].get("src_ip"))
            has_window = bool(pt.get("window_evidence") and pt["window_evidence"].get("signature_category"))
            has_bn = bool(pt.get("bn_attributions") is not None)
            has_hmm = bool(pt.get("hmm_transition") and pt["hmm_transition"].get("next_step_projection"))
            has_dn = bool(pt.get("decision_network_evaluation") and pt["decision_network_evaluation"].get("chosen_action"))
            has_rationale = bool(pt.get("rationale") and len(pt["rationale"]) > 10)

            if not has_raw: missing_components["missing_raw_alert"] += 1
            if not has_window: missing_components["missing_window_evidence"] += 1
            if not has_bn: missing_components["missing_bn_attributions"] += 1
            if not has_hmm: missing_components["missing_hmm_transition"] += 1
            if not has_dn: missing_components["missing_dn_evaluation"] += 1
            if not has_rationale: missing_components["missing_rationale"] += 1

            if has_raw and has_window and has_bn and has_hmm and has_dn and has_rationale:
                valid_traces += 1
                if sample_trace is None:
                    sample_trace = pt

        audit_passed = (valid_traces == traces_checked)
        coverage_pct = round((valid_traces / max(1, traces_checked)) * 100, 2)

        out = {
            "rq": "RQ5",
            "title": "Automated Provenance & Explainability Audit",
            "total_recommendations_audited": traces_checked,
            "valid_audit_traces": valid_traces,
            "provenance_coverage_pct": coverage_pct,
            "audit_passed": audit_passed,
            "missing_components": dict(missing_components),
            "sample_provenance_trace": sample_trace,
        }
        self.db.save_experiment_result("RQ5", out)
        return out

    def run_ablation_study(self, scenario_name: str = "events_lldos1") -> Dict[str, Any]:
        """
        Runs B0, B1, B2, and B3 on the same event stream to compute comparative ablation metrics.
        - B0: Rule-based baseline
        - B1: BN-only
        - B2: BN + HMM
        - B3: Full Pipeline (BN + HMM + Decision Network)
        """
        events = self.db.get_events(scenario_name, limit=600)
        from app.config import UTILITY_MATRIX

        ablation_metrics = {}
        for mode in ["B0", "B1", "B2", "B3"]:
            self.pipeline.reset_stream_state()
            correct_states = 0
            false_alarms = 0
            utilities = []
            ttd_steps = None  # Time to detection for phase >= 3

            for step_idx, e in enumerate(events):
                out = self.pipeline.process_event(e, ablation_mode=mode)
                true_phase = e["true_phase_label"]
                true_state = THREAT_STATES[true_phase]
                dom_state = out["recommendation"]["dominant_state"]
                action = out["recommendation"]["recommended_action"]

                if dom_state == true_state:
                    correct_states += 1

                # False alarm: took aggressive action (Block or Isolate) when state was Benign or Recon
                if true_phase in [0, 1] and action in ["Block", "Isolate"]:
                    false_alarms += 1

                # Time to detection: first time system flags compromise / priv_esc / attack
                if ttd_steps is None and true_phase >= 3 and action in ["Block", "Isolate"]:
                    ttd_steps = step_idx + 1

                u = UTILITY_MATRIX[true_state][action]
                utilities.append(u)

            ablation_metrics[mode] = {
                "name": {
                    "B0": "B0: Rule-Based Baseline",
                    "B1": "B1: BN-Only (Static)",
                    "B2": "B2: BN + HMM (Heuristic)",
                    "B3": "B3: Full Pipeline (BN+HMM+DN)"
                }[mode],
                "accuracy": round(correct_states / max(1, len(events)), 4),
                "false_alarm_rate": round(false_alarms / max(1, len(events)), 4),
                "mean_utility": round(float(np.mean(utilities)), 2),
                "time_to_detection_steps": ttd_steps if ttd_steps is not None else -1,
            }

        out = {
            "scenario": scenario_name,
            "total_alerts": len(events),
            "configurations": ablation_metrics,
        }
        self.db.save_experiment_result(f"ablation_{scenario_name}", out)
        return out

import sys
import json
import time
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.config import DB_PATH, EXPERIMENTS_DIR
from app.ingestion.database import Database
from app.evaluation.experiment_runner import ExperimentRunner

def main():
    print("=" * 70)
    print("Executing Empirical Evaluation Suite: RQ1 - RQ5 + Pipeline Ablation")
    print("=" * 70)

    db = Database(DB_PATH)
    runner = ExperimentRunner(db)
    t0 = time.time()

    # RQ1: BN Phase Inference & Calibration
    print("\n>>> Running RQ1: BN Phase Inference & Calibration Analysis...")
    rq1 = runner.run_rq1_bn_inference()
    print(f"    - Accuracy: {rq1['accuracy'] * 100:.2f}%")
    print(f"    - Macro F1: {rq1['macro_f1']:.4f}")
    print(f"    - Expected Calibration Error (ECE): {rq1['expected_calibration_error_ece']:.4f}")
    print(f"    - Brier Score: {rq1['brier_score']:.4f}")
    with open(EXPERIMENTS_DIR / "rq1_bn_inference.json", "w") as f:
        json.dump(rq1, f, indent=2)

    # RQ2: HMM Next-Phase Prediction
    print("\n>>> Running RQ2: HMM Next-Phase Prediction vs Naive Baseline...")
    rq2 = runner.run_rq2_hmm_prediction()
    for sc, res in rq2["results"].items():
        print(f"    [{sc}]:")
        print(f"      - HMM 1-Step Accuracy: {res['hmm_1step_accuracy']*100:.2f}% vs Baseline: {res['baseline_1step_accuracy']*100:.2f}% (Gain: {res['relative_gain_1step']*100:+.2f}%)")
        print(f"      - HMM 2-Step Accuracy: {res['hmm_2step_accuracy']*100:.2f}% vs Baseline: {res['baseline_2step_accuracy']*100:.2f}%")
    with open(EXPERIMENTS_DIR / "rq2_hmm_prediction.json", "w") as f:
        json.dump(rq2, f, indent=2)

    # RQ3: Decision Network Expected Utility vs Fixed Rules
    print("\n>>> Running RQ3: Decision Network Utility & Regret Evaluation...")
    rq3 = runner.run_rq3_decision_utility()
    print(f"    - Decision Network Mean Expected Utility: {rq3['mean_dn_utility']:.2f}")
    print(f"    - Fixed Heuristic Rules Mean Utility:   {rq3['mean_rule_utility']:.2f}")
    print(f"    - Relative Utility Gain:                {rq3['utility_improvement']:+.2f}")
    print(f"    - Decision Regret Reduction:            {rq3['regret_reduction_pct']:.1f}%")
    with open(EXPERIMENTS_DIR / "rq3_decision_utility.json", "w") as f:
        json.dump(rq3, f, indent=2)

    # RQ4: Generalization & Robustness (LLDOS 2.0.2 & Sensitivity)
    print("\n>>> Running RQ4: Generalization Drop & Robustness Sensitivity...")
    rq4 = runner.run_rq4_generalization_and_robustness()
    gen = rq4["cross_scenario_generalization"]
    print(f"    - In-Distribution (LLDOS 1.0) Accuracy:  {gen['lldos1_in_distribution_accuracy']*100:.2f}%")
    print(f"    - Out-of-Distribution (LLDOS 2.0.2) Accuracy: {gen['lldos2_stealthier_out_of_distribution_accuracy']*100:.2f}%")
    print(f"    - Generalization Drop Delta:             {gen['generalization_delta']*100:+.2f}%")
    print(f"    - Synthesized Noise Curve Evaluated (0% - 50% Noise)")
    print(f"    - Missing Alert Evasion Curve Evaluated (0% - 40% Evasion)")
    with open(EXPERIMENTS_DIR / "rq4_generalization_robustness.json", "w") as f:
        json.dump(rq4, f, indent=2)

    # RQ5: Automated Provenance Audit
    print("\n>>> Running RQ5: Automated Provenance & Explainability Audit...")
    rq5 = runner.run_rq5_provenance_audit()
    print(f"    - Total Recommendations Audited: {rq5['total_recommendations_audited']}")
    print(f"    - Valid Provenance Traces:       {rq5['valid_audit_traces']}")
    print(f"    - Provenance Coverage:           {rq5['provenance_coverage_pct']:.1f}%")
    print(f"    - Audit Passed:                  {rq5['audit_passed']}")
    with open(EXPERIMENTS_DIR / "rq5_provenance_audit.json", "w") as f:
        json.dump(rq5, f, indent=2)

    # Ablation Study across scenarios
    print("\n>>> Running Ablation Study (B0 -> B3) across Scenarios...")
    ablation_lldos1 = runner.run_ablation_study("events_lldos1")
    ablation_lldos2 = runner.run_ablation_study("events_lldos2")
    ablation_synthetic = runner.run_ablation_study("events_synthetic")

    all_ablations = {
        "LLDOS_1.0": ablation_lldos1,
        "LLDOS_2.0.2": ablation_lldos2,
        "Synthetic": ablation_synthetic,
    }
    with open(EXPERIMENTS_DIR / "ablation_b0_b3.json", "w") as f:
        json.dump(all_ablations, f, indent=2)

    print("\n" + "=" * 70)
    print(f"All Experiments Completed Successfully in {time.time() - t0:.2f}s!")
    print(f"Artifacts saved to: {EXPERIMENTS_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()

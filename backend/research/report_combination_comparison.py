"""Report component experiments separately from published score comparisons."""
import csv
import json

import numpy as np

from compare_combinations import OUT, LABELS


def report():
    results = json.loads((OUT / "fold_results.json").read_text())
    summary = json.loads((OUT / "summary.json").read_text())
    equivalence = json.loads((OUT / "hmm_equivalence.json").read_text())
    assert len(results) == 72 and len(equivalence) == 8
    assert max(r["max_absolute_forecast_difference"] for r in equivalence) < 1e-12
    for r in results:
        assert len(r["train"]) == len(set(r["train"])) == 6
        assert r["test"] not in r["train"] and r["validation"] not in r["train"]
        assert r["test"] != r["validation"]
    rows = []
    for r in results:
        for scoring in ["scores", "calibrated_scores"]:
            for h, v in r[scoring].items():
                rows.append({"test": r["test"], "mode": r["mode"], "scoring": scoring,
                             "horizon_minutes": h, **{k: value for k, value in v.items() if k != "decision_assumptions"}})
    with (OUT / "all_scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    rng = np.random.default_rng(271828)
    comparisons = []
    for a, b in [("exact", "bn_no_filter"), ("exact", "standard_hmm"),
                 ("exact", "direct_logistic"), ("exact", "temporal_logistic"),
                 ("exact", "temporal_boosting"), ("soft", "exact")]:
        for scoring in ["scores", "calibrated_scores"]:
            for h in ["5", "15", "30"]:
                for metric in ["brier", "pr_auc"]:
                    left = {r["test"]: r[scoring][h][metric] for r in results if r["mode"] == a}
                    right = {r["test"]: r[scoring][h][metric] for r in results if r["mode"] == b}
                    assert left.keys() == right.keys() and len(left) == 8
                    delta = np.array([left[k] - right[k] for k in sorted(left)])
                    resampled = rng.choice(delta, size=(10000, 8), replace=True).mean(axis=1)
                    comparisons.append({"method": a, "baseline": b, "scoring": scoring,
                        "horizon_minutes": int(h), "metric": metric,
                        "mean_difference_method_minus_baseline": float(delta.mean()),
                        "descriptive_bootstrap_interval": np.quantile(resampled, [.025, .975]).tolist(),
                        "per_scenario_differences": dict(zip(sorted(left), delta.tolist()))})
    (OUT / "paired_comparisons.json").write_text(json.dumps(comparisons, indent=2), encoding="utf-8")
    fifteen = summary["exact"]["calibrated_scores"]["15"]
    bn = summary["bn_no_filter"]["calibrated_scores"]["15"]
    reduction = (bn["mean_brier"] - fifteen["mean_brier"]) / bn["mean_brier"] * 100
    lines = ["# Are our combinations better than other work?", "", "Assessment: 4 October 2026.", "",
        "**No demonstrated superiority over published cyberattack-forecasting systems.** "
        "Component tests show a useful ranking contribution from temporal filtering, but the present "
        "BN-HMM is mathematically the same forecaster as a conventional HMM with factorized categorical "
        "emissions. The uncertain-association addition has mixed results. Published results inspected "
        "below do not match our dataset, endpoint, horizons, and evaluation protocol, and none of those "
        "complete named systems was reproduced in this extension.", "",
        "## Same-data component and standard-method experiments", "",
        "Eight AIT-ADS scenarios; six fitting, one calibration, one test scenario per rotating fold. "
        "All predictions use past-only observations on a 60-second clock. The endpoint is scheduled "
        "privilege escalation. New alternatives use ordinary exact deduplication. Temporal supervised "
        "baselines use current count buckets and trailing 5- and 15-minute means. Settings were written "
        "in [the extension protocol](../combination_comparison_protocol.md) before their outcome scoring. "
        "The original five comparisons are reused after verifying exact BN-HMM reproduction.", "",
        f"At 15 minutes, temporal filtering reduces calibrated Brier by {reduction:.2f}% versus the "
        f"no-filter ablation and raises scenario-averaged average precision from {bn['mean_average_precision']:.4f} "
        f"to {fifteen['mean_average_precision']:.4f}. However, every tested method warns about zero of eight "
        "outcomes at that horizon under the specified threshold-selection rule. Better ranking therefore "
        "has not produced useful warnings at that operating point. Direct logistic forecasting has "
        "slightly lower 15-minute Brier than BN-HMM but much lower average precision; no method wins "
        "every metric. The positive timestamps are rare, so Brier alone is insufficient.", "",
        "The no-filter ablation uses a training-derived fixed state-occupancy prior and the same "
        "learned Markov onset projection. It removes sequential filtering, but is not a pure static "
        "BN forecasting algorithm. The independent conventional HMM implementation matches BN-HMM "
        f"raw predictions on all held-out bins with maximum absolute difference "
        f"{max(r['max_absolute_forecast_difference'] for r in equivalence):.3g}. Separate calibration fits "
        "can amplify floating-point differences slightly; their aggregate scores are effectively equal. "
        "Thus there is no measured improvement attributable merely to calling its observation model a BN.", "",
        "The same hypothetical binary decision rule is applied to every forecast. It assumes a false "
        "action cost of 1, missed imminent outcome cost of 20, and perfect immediate action effect. "
        "This does not test the complete Decision Network policy or measured prevention. A downstream "
        "response policy does not change forecast accuracy unless it changes subsequent observations/outcomes.", ""]
    for scoring in ["scores", "calibrated_scores"]:
        lines += [f"### {scoring}", "",
                  "Brier lower is better; AP higher is better. Each score is scenario-averaged.", "",
                  "| Horizon | Method | Brier | AP | Warned / 8 | False episodes | Negative warning minutes | Modeled cost |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        for h in ["5", "15", "30"]:
            for mode, label in LABELS.items():
                v = summary[mode][scoring][h]
                lines.append(f"| {h} min | {label} | {v['mean_brier']:.6f} | {v['mean_average_precision']:.4f} | {v['warned_episodes']}/8 | {v['false_warning_episodes']} | {v['negative_warning_minutes']:.0f} | {v['mean_modeled_decision_cost']:.5f} |")
        lines.append("")
    lines += ["## Published work checked and why its scores cannot be ranked against ours", "",
        "| Work | What is established by the inspected primary source | Comparison status |",
        "|---|---|---|",
        "| [Devarakonda et al., 2012: BN + HMM](https://www.sciencedirect.com/science/article/pii/S221201731200360X) | Publisher abstract describes KDDCUP normal/attack connection classification and a BN structure used for HMM transitions. | Detection target differs from scheduled-onset forecasting; not reproduced. |",
        "| [Sendi et al., 2012: optimized alerts + HMM](https://citeseerx.ist.psu.edu/document?doi=3aa6e5a9a9bfb27bf32fbab8b2c194ab42bad1dc&repid=rep1&type=pdf) | Indexed original abstract reports multistep prediction on Lincoln Laboratory 2000 data. | Closely related objective, different benchmark/protocol; full text unavailable in this check. |",
        "| [Li et al., 2020: hidden Markov + probabilistic inference](https://www.sciencedirect.com/science/article/abs/pii/S0167404820302479) | Indexed publisher preview describes attack-plan reasoning. | Relevant integration precedent; complete methods/results not reverified or reproduced here. |",
        "| [Ingale et al., 2020: HMM + Naive Bayes](https://ieeexplore.ieee.org/document/9155895) | Primary IEEE record verifies the titled combination. | Full method, dataset, and numerical results unavailable; cannot infer them from citations to the work. |",
        "| [Zhang et al., 2022: pre-trained HMM](https://www.mdpi.com/1424-8220/22/8/2874) | Author article describes attack-stage detection on DARPA, DEFCON21, and ISCXIDS2012; experiment alerts contain no benign examples. | Stage-decoding accuracy differs from pre-onset warnings with negative exposure. |",
        "| [PARD-SSM, April 2026 preprint](https://arxiv.org/html/2604.02299v1) | Reports F1 0.982 on CICIDS2017, 0.971 on UNSW-NB15, and about eight minutes of early warning; Section 9.5 describes smoothed posteriors. | Different outcomes/splits; causal filtering versus smoothing must be clarified before a fair online comparison. Claims not independently reproduced. |",
        "| [AlertBERT, February 2026 preprint](https://arxiv.org/html/2602.06534v1) | Groups alerts on AIT-derived augmented data and evaluates pairwise clustering ROC/AUC. [Author code](https://github.com/ait-aecid/AlertBERT) is available. | Same source dataset family, different grouping target/metric; no forecast comparison completed. |", "",
        "AlertBERT is a concrete external grouping comparator for a later experiment: apply a "
        "causal version of its grouping to the same forecaster and score the same future-onset targets. "
        "Its reported embedding readout pads each sequence on both ends, so simply replaying the "
        "published forensic evaluation as an online predictor could use later alerts. Verify availability "
        "of every input, fit embeddings/grouping parameters on fitting runs only, and label any "
        "adaptation rather than claiming exact reproduction.", "",
        "## Limits and claim supported", "",
        "This is an exploratory eight-scenario pilot with related attack templates, very few outcomes, "
        "one calibration run per fold, and a coarse warning threshold grid. Baseline settings were fixed "
        "rather than exhaustively tuned. The association matcher lacks real event-identity validation. "
        "Stage timestamps remain scheduled labels, not independently verified successful compromises. "
        "Retrospective alert timestamps are assumed to represent availability. All limitations in the "
        "[first pilot report](../evidence_pilot/REPORT.md) still apply. Campaign-resampling intervals "
        "in paired_comparisons.json are descriptive; overlapping training folds and related scenarios "
        "preclude treating them as confirmatory significance tests.", "",
        "The defensible conclusion is that temporal filtering improves ranking over the no-filter "
        "ablation in this pilot, while the chosen BN-HMM observation model is equivalent to a standard "
        "HMM. Overall forecasting superiority, an advantage from the complete three-unit combination, "
        "and superiority over named published methods remain unestablished.", "",
        "## Reproduce", "", "```powershell",
        "python backend/research/compare_combinations.py",
        "python backend/research/report_combination_comparison.py", "```", "",
        "Requires the prepared AIT-ADS inputs and completed original pilot. All 72 natural-trace "
        "scenario/method evaluations, 432 score rows, equivalence checks, and paired comparisons are "
        "preserved in this directory. Source hashes are in source_sha256.json; runtime versions are "
        "recorded in ../evidence_pilot/reproducibility.json."]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Verified 72 evaluations, disjoint splits, and per-bin HMM equivalence; report written.")


if __name__ == "__main__":
    report()

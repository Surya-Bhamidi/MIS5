"""Generate an auditable comparison without cherry-picking folds/horizons."""
from pathlib import Path
import csv
import hashlib
import json
import platform
import sys

import numpy as np
import scipy
import sklearn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments" / "evidence_pilot"
MODES = ["raw", "exact", "hard", "soft", "direct_logistic"]
LABELS = {"raw": "Separate reports", "exact": "Exact deduplication",
          "hard": "Tuned deterministic grouping", "soft": "Association-mixture prototype",
          "direct_logistic": "Direct logistic forecaster"}


def report():
    results = json.loads((OUT / "fold_results.json").read_text())
    summary = json.loads((OUT / "summary.json").read_text())
    assert len(results) == 8 * 5 * 3, "Incomplete experiment"
    for r in results:
        assert r["test"] not in r["train"] and r["validation"] not in r["train"]
        assert r["test"] != r["validation"] and len(r["train"]) == 6
        if r["condition"] == "exact_replay" and r["mode"] != "raw":
            assert r["max_forecast_change_from_natural"] == 0.0
    flat = []
    for r in results:
        for scoring in ["scores", "calibrated_scores"]:
            for horizon, v in r[scoring].items():
                flat.append({"test": r["test"], "validation": r["validation"],
                             "mode": r["mode"], "condition": r["condition"],
                             "scoring": scoring, "horizon_minutes": int(horizon),
                             **{k: value for k, value in v.items() if k != "decision_assumptions"}})
    with (OUT / "all_scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    rng = np.random.default_rng(271828)
    comparisons = []
    for condition in summary:
        for scoring in ["scores", "calibrated_scores"]:
            for horizon in ["5", "15", "30"]:
                for baseline in ["exact", "hard", "direct_logistic"]:
                    a = sorted([r for r in results if r["condition"] == condition and r["mode"] == "soft"], key=lambda r: r["test"])
                    b = sorted([r for r in results if r["condition"] == condition and r["mode"] == baseline], key=lambda r: r["test"])
                    delta = np.array([x[scoring][horizon]["brier"] - y[scoring][horizon]["brier"] for x, y in zip(a, b)])
                    bootstrap = rng.choice(delta, size=(10000, len(delta)), replace=True).mean(axis=1)
                    base_score = summary[condition][baseline][scoring][horizon]["mean_brier"]
                    comparisons.append({"condition": condition, "scoring": scoring, "horizon_minutes": int(horizon),
                                        "baseline": baseline, "mean_brier_delta_soft_minus_baseline": float(delta.mean()),
                                        "relative_brier_reduction_percent": float(-delta.mean() / base_score * 100),
                                        "descriptive_bootstrap_interval": np.quantile(bootstrap, [.025, .975]).tolist(),
                                        "folds_better": int(np.sum(delta < -1e-12)),
                                        "folds_worse": int(np.sum(delta > 1e-12)),
                                        "folds_tied": int(np.sum(np.abs(delta) <= 1e-12)),
                                        "per_scenario_deltas": {x["test"]: float(d) for x, d in zip(a, delta)}})
    (OUT / "paired_comparisons.json").write_text(json.dumps(comparisons, indent=2), encoding="utf-8")
    manifest = {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
                "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
                "source_sha256": {}, "split": "6 train / 1 calibration / 1 test, rotated over eight scenarios",
                "clock_seconds": 60, "endpoint": "scheduled privilege escalation start",
                "result_status": "exploratory pilot; academic novelty and generalization unestablished"}
    for name in ["evidence_pilot.py", "report_evidence_pilot.py", "fetch_ait.py"]:
        path = ROOT / "backend" / "research" / name
        manifest["source_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "reproducibility.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = ["# Evidence-association improvement pilot", "", "Completed 4 October 2026.", "",
             "This evaluates a bounded association-mixture prototype on eight AIT-ADS simulated scenarios. "
             "All models use the same 60-second grid and held-out scenario splits. The endpoint is scheduled "
             "privilege escalation, not DDoS launch or independently verified successful compromise.", "",
             "## Verdict", "",
             "**This first prototype does not establish a convincing forecasting improvement or academic novelty.** "
             "On natural traces, its calibrated Brier score is worse than exact deduplication at all three horizons. "
             "At 15 minutes, Brier is 0.002630 versus 0.002577 for exact deduplication (2.09% worse), "
             "0.002728 for tuned deterministic grouping (3.58% better), and 0.002572 for direct logistic forecasting. "
             "The descriptive interval for its advantage over deterministic grouping includes zero. "
             "All five methods warn about zero of eight outcomes at this horizon under the specified validation-selected rule.", "",
             "There are limited positive findings: natural-trace 15-minute average precision rises from 0.0703 "
             "with exact deduplication to 0.0726 with the prototype, and under the constructed alias/jitter stress "
             "it is 0.0797 versus 0.0345. These are ranking improvements in this pilot, not demonstrated "
             "improvements in reliable early warnings, real cross-sensor event association, or prevention. "
             "The stress mechanism resembles the constructed positives used to fit the matcher; transfer to "
             "other corruption mechanisms has not been tested. At 30 minutes on natural traces the calibrated "
             "prototype warns about one of eight outcomes and produces 26 false-warning episodes, compared "
             "with one outcome and 25 false episodes for exact deduplication.", "",
             "Improvement can support an empirical paper contribution when the comparison is fair and reproducible. "
             "It does not establish that a method is original. The appropriate current claim is an exploratory "
             "evaluation with mixed results; a superiority or first-ever method claim is unsupported. "
             "This evaluates a limited prototype, so it also does not rule out a better event-association model.", "",
             "## Complete outcome comparison", "",
             "Brier is averaged across test scenarios; lower is better. AP is scenario-averaged average precision "
             "computed with sklearn.metrics.average_precision_score, not trapezoidal PR-curve area. "
             "The JSON field names pr_auc and mean_pr_auc are retained for compatibility and denote AP. "
             "Positive forecast timestamps are rare, so a low Brier alone is insufficient evidence of useful forecasting. "
             "Warnings use a validation-selected budget of at most one false-warning episode per 24 hours "
             "of negative forecast exposure and at most five negative warning minutes on the validation scenario. "
             "That budget is not guaranteed on test scenarios. Lead time includes only warned outcomes; misses are shown.", ""]
    for condition in ["natural", "exact_replay", "alias_jitter"]:
        lines.extend([f"### {condition}", ""])
        for scoring in ["scores", "calibrated_scores"]:
            lines.extend([f"**{scoring}**", "", "| Horizon | Method | Brier | AP | Warned / 8 | Median lead, min | False warning episodes | Negative warning minutes | Modeled cost |",
                          "|---|---|---:|---:|---:|---:|---:|---:|---:|"])
            for horizon in ["5", "15", "30"]:
                for mode in MODES:
                    v = summary[condition][mode][scoring][horizon]
                    lead = "—" if v["median_lead_minutes_when_warned"] is None else f"{v['median_lead_minutes_when_warned']:.2f}"
                    lines.append(f"| {horizon} min | {LABELS[mode]} | {v['mean_brier']:.6f} | {v['mean_pr_auc']:.4f} | {v['warned_episodes']}/8 | {lead} | {v['false_warning_episodes']} | {v['negative_warning_minutes']:.0f} | {v['mean_modeled_decision_cost']:.5f} |")
            lines.append("")
    lines.extend(["## Paired differences on natural traces", "",
                  "Negative Brier differences favor the prototype. Bootstrap intervals below are descriptive "
                  "scenario-resampling intervals, not confirmatory significance tests: training folds overlap and "
                  "the eight scenarios share related attack templates. No multiple-comparison-adjusted success claim is made.", "",
                  "| Scoring | Horizon | Baseline | Mean Brier difference | Descriptive interval | Better / worse / tied folds |",
                  "|---|---|---|---:|---|---|"])
    for row in comparisons:
        if row["condition"] != "natural":
            continue
        lo, hi = row["descriptive_bootstrap_interval"]
        lines.append(f"| {row['scoring']} | {row['horizon_minutes']} min | {LABELS[row['baseline']]} | {row['mean_brier_delta_soft_minus_baseline']:.7f} | [{lo:.7f}, {hi:.7f}] | {row['folds_better']} / {row['folds_worse']} / {row['folds_tied']} |")
    lines.extend(["", "## Checks and limitations", "",
                  "- All eight splits have disjoint fitting, calibration, and test scenario identities. Nine numerical/causal pilot invariants passed before scoring.",
                  "- Exact replays produce precisely zero forecast change for exact deduplication, deterministic grouping, the association prototype, and the direct forecaster. This is a correctness property, not a unique advantage of the proposed method.",
                  "- Alias/jitter stress adds copies to 10% of existing records, with changed report IDs and 0.05–2 second timestamp delays. Natural results remain the main comparison; only one fixed stress seed per held-out scenario was used.",
                  "- The matcher uses constructed replay positives and different original records as proxy negatives. Different stored reports may refer to the same real event. Real event-identity truth and genuine cross-sensor corroboration have not been validated.",
                  "- The prototype marginalizes disjoint report pairs into count-bucket likelihoods. It assumes state-independent association weights and conditional independence of count categories. It does not implement a globally coherent model of all latent event identities and sensor error dependencies.",
                  "- Count bins and broad observable message categories are a limited representation; this study does not rule out other observation models. Models are fitted separately to their corresponding evidence representation, and deterministic grouping tolerance is selected on validation data.",
                  "- Alert timestamps are treated as availability timestamps for retrospective replay. Actual live collection delays and telemetry health are not measured. Start exposure is the UTC day containing the first retained alert; initial unobserved minutes may be counted as empty observations.",
                  "- Scheduled attack-stage labels are the target. Exfiltration was excluded because onset ordering was inconsistent in six published scenario label sequences; raw victim/attacker logs still need independent validation for a submission.",
                  "- Each run contributes one attack outcome; the long background traces do not create thousands of independent positive episodes. Training and calibration use six and one scenarios respectively, so calibration and warning thresholds may vary substantially.",
                  "- The modeled response cost uses the same binary Monitor/Block expected-cost decision for every method: false action cost 1, missed imminent outcome cost 20, assumed perfect immediate action effect. The threshold is 1/21. It is a hypothetical, framewise decision analysis, not measured prevention or the dashboard's full response policy.",
                  "- Separate calibration models are fitted on the validation scenario for each horizon, with monotonic horizon correction. This is exploratory calibration with very few positive outcomes.",
                  "- The warning rule considers a fixed grid of thresholds and may select no warnings. These results describe that rule, not the best achievable warning policy at every operating point.",
                  "", "## Reproduce", "", "```powershell", "python backend/research/fetch_ait.py", "python backend/research/evidence_pilot.py prepare", "python backend/research/evidence_pilot.py checks", "python backend/research/evidence_pilot.py run", "python backend/research/report_evidence_pilot.py", "```", "",
                  "Inputs: [AIT-ADS](https://zenodo.org/records/8263181); download checksums are verified against the publisher record. "
                  "Original dashboard experiments and SQLite tables were not used for these outcome scores. "
                  "All fold-level scores, transformations, code, and runtime versions are preserved alongside this report."])
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Verified 120 experiment records and all replay invariants; report written.")
    for c in comparisons:
        if c["condition"] == "natural" and c["scoring"] == "calibrated_scores":
            print(json.dumps(c))


if __name__ == "__main__":
    report()

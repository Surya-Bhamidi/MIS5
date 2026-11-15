"""Export focused presentation figures from existing, verified campaign results."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Plots" / "Results" / "mids"
FULL = "aminer+suricata+wazuh"
MODES = ["temporal_boosting", "conditional_fusion", "pooled_counts", "pooled_fixed_blend"]
LABELS = ["Original\ncounts-only", "Earlier\nduration/tree hybrid", "Matched pooled\ncounts-only", "Current hybrid\n25% state blend"]
COLORS = ["#4379aa", "#8064a2", "#87939e", "#159b87"]
SOURCES = [
    "experiments/current_version/summary.json",
    "experiments/current_version/config.json",
    "experiments/current_version/verification.json",
    "experiments/selective_fusion/summary.json",
    "experiments/selective_fusion/scored.json",
    "experiments/published_comparison/budget_summary.json",
    "experiments/published_comparison/budget_fold_results.json",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def matches(row, mode, horizon):
    common = (row["mode"] == mode and row["horizon"] == horizon
              and row["endpoint"] == "successful_root" and row["budget"] == 1)
    if mode in MODES[2:]:
        common = common and row["available"] == FULL and row["delay_minutes"] == 0
    return common


def write_table(name, rows):
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def finish(fig, name, note):
    fig.text(.5, .038, note, ha="center", va="bottom", fontsize=10, color="#475569", linespacing=1.5)
    fig.tight_layout(rect=(.01, .17, .99, .87))
    fig.savefig(OUT / f"{name}.png", dpi=300, facecolor="white")
    fig.savefig(OUT / f"{name}.pdf", facecolor="white")
    plt.close(fig)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    before = {p: digest(ROOT / p) for p in SOURCES}
    current, config, verified, matched, new_cases, old, old_cases = [read(p) for p in SOURCES]
    assert config["forecast_mode"] == MODES[-1] and config["state_branch_weight"] == .25
    assert config["primary_horizon_minutes"] == 30 and verified["passed"]
    summaries, per_campaign = [], []
    for horizon in [15, 30]:
        for mode, label in zip(MODES, LABELS):
            source = old if mode in MODES[:2] else current if mode == MODES[-1] else matched
            found = [r for r in source if matches(r, mode, horizon)]
            assert len(found) == 1
            row = dict(model=label.replace("\n", " "), **found[0])
            cases = [r for r in (old_cases if mode in MODES[:2] else new_cases) if matches(r, mode, horizon)]
            assert len(cases) == row["campaigns"] == 8
            assert len({r["scenario"] for r in cases}) == 8
            assert sum(r["strict_warning_recall"] for r in cases) == row["strict_warned"]
            assert sum(r["false_warning_episodes"] for r in cases) == row["false_episodes"]
            assert sum(r["negative_warning_minutes"] for r in cases) == row["negative_warning_minutes"]
            for key, case_key in [("mean_brier", "brier"), ("mean_ap", "average_precision")]:
                np.testing.assert_allclose(row[key], np.mean([r[case_key] for r in cases]), rtol=0, atol=1e-12)
            summaries.append(row)
            if horizon == 30:
                per_campaign.extend(dict(model=row["model"], **r) for r in cases)

    write_table("all_metrics_15_30_minutes", summaries)
    write_table("campaign_results_30_minutes", per_campaign)
    rows = [r for r in summaries if r["horizon"] == 30]
    write_table("plotted_metrics_30_minutes", rows)
    original, earlier, control, hybrid = rows
    assert hybrid["strict_warned"] > max(r["strict_warned"] for r in rows[:-1])
    assert hybrid["mean_brier"] < min(r["mean_brier"] for r in rows[:-1])
    gains = {
        "coverage_percent": 100 * hybrid["strict_warned"] / 8,
        "coverage_gain_vs_matched_percentage_points": 100 * (hybrid["strict_warned"] - control["strict_warned"]) / 8,
        "brier_reduction_vs_matched_percent": 100 * (1 - hybrid["mean_brier"] / control["mean_brier"]),
        "brier_reduction_vs_original_percent": 100 * (1 - hybrid["mean_brier"] / original["mean_brier"]),
        "matched_false_episodes": control["false_episodes"],
        "hybrid_false_episodes": hybrid["false_episodes"],
        "matched_average_precision": control["mean_ap"],
        "hybrid_average_precision": hybrid["mean_ap"],
    }
    (OUT / "claim_values.json").write_text(json.dumps(gains, indent=2), encoding="utf-8")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42})
    context = "8 AIT campaigns | Full sensors | Verified successful-root outcome | Project versions, not published systems"
    caveat = "Exploratory 30-minute result; the preset was selected after reviewing these campaigns."
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fig.suptitle("30-minute timely-warning coverage", fontsize=23, fontweight="bold", y=.97)
    fig.text(.5, .90, "Current hybrid: 5/8 campaigns warned in time; matched counts: 3/8", ha="center", fontsize=13)
    values = [100 * r["strict_warned"] / 8 for r in rows]
    bars = ax.bar(range(4), values, color=COLORS, width=.6)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 25), [f"{v}%" for v in range(0, 101, 25)])
    ax.set_ylabel("Campaigns with a timely new warning (higher is better)")
    ax.set_xticks(range(4), LABELS)
    ax.set_axisbelow(True); ax.grid(axis="y", alpha=.2)
    for bar, row, value in zip(bars, rows, values):
        ax.annotate(f'{row["strict_warned"]}/8 ({value:.1f}%)', (bar.get_x() + bar.get_width()/2, value),
                    xytext=(0, 8), textcoords="offset points", ha="center", fontweight="bold", fontsize=14)
    finish(fig, "01_timely_warning_coverage", context + "\nMatched comparison tradeoff: false episodes 1 -> 5; new warning starts within 30 minutes before the outcome.\n" + caveat)

    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fig.suptitle("30-minute probability error: Brier score", fontsize=23, fontweight="bold", y=.97)
    fig.text(.5, .90, f'Hybrid error is {gains["brier_reduction_vs_matched_percent"]:.2f}% lower than matched counts and '
             f'{gains["brier_reduction_vs_original_percent"]:.2f}% lower than original counts', ha="center", fontsize=13)
    values = [r["mean_brier"] * 1000 for r in rows]
    bars = ax.bar(range(4), values, color=COLORS, width=.6)
    ax.set_ylim(0, 2.5)
    ax.set_ylabel("Mean Brier score x 1,000 (lower is better)")
    ax.set_xticks(range(4), LABELS)
    ax.set_axisbelow(True); ax.grid(axis="y", alpha=.2)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:.4f}", (bar.get_x() + bar.get_width()/2, value), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontweight="bold", fontsize=14)
    finish(fig, "02_probability_error", context + "\nBrier is probability error, not accuracy; the matched-baseline gain is small and is not a significance claim.\n" + caveat)

    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fig.suptitle("30-minute coverage and false-alarm tradeoff", fontsize=23, fontweight="bold", y=.97)
    fig.text(.5, .90, "The hybrid has the highest coverage; matched counts has the fewest false episodes", ha="center", fontsize=13)
    offsets = [(0, -38), (12, -12), (12, -12), (14, 8)]
    for row, label, color, offset in zip(rows, LABELS, COLORS, offsets):
        coverage = row["strict_warned"] / 8 * 100
        ax.scatter(row["false_episodes"], coverage, s=190, color=color, zorder=3, edgecolor="white")
        ax.annotate(label.replace("\n", " ") + f'\n{row["strict_warned"]}/8; {row["false_episodes"]} false episodes',
                    (row["false_episodes"], coverage), xytext=offset, textcoords="offset points",
                    ha="center" if offset[0] == 0 else "left", va="top" if offset[1] < 0 else "bottom", fontsize=11)
    ax.set_xlim(0, 22); ax.set_xticks(range(0, 23, 2))
    ax.set_ylim(0, 100); ax.set_yticks(range(0, 101, 25), [f"{v}%" for v in range(0, 101, 25)])
    ax.set_xlabel("False-alarm episodes (lower is better)")
    ax.set_ylabel("Timely-warning coverage (higher is better)")
    ax.grid(alpha=.2)
    finish(fig, "03_alarm_tradeoff", context + "\nThresholds selected under the same validation budget; this does not guarantee the test alarm rate.\n" + caveat)

    sensitivity = []
    for mode in MODES:
        cases = [r for r in per_campaign if r["mode"] == mode and r["scenario"] != "wheeler"]
        sensitivity.append(dict(mode=mode, campaigns=len(cases), strict_warned=sum(r["strict_warning_recall"] for r in cases),
                                false_episodes=sum(r["false_warning_episodes"] for r in cases)))
    write_table("without_wheeler_sensitivity", sensitivity)
    assert before == {p: digest(ROOT / p) for p in SOURCES}
    manifest = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Focused export of existing exploratory results; no fitting, tuning or new test campaigns",
        "source_sha256": before,
        "script_sha256": digest(Path(__file__)),
        "checks": {"eight_unique_campaigns_per_model": True, "counts_and_means_reconstructed_from_folds": True,
                   "hybrid_leads_on_selected_30_minute_metrics": True, "original_sources_unchanged": True},
        "output_sha256": {p.name: digest(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"folder": str(OUT), "figures": 3, "gains": gains, "checks": manifest["checks"]}, indent=2))


if __name__ == "__main__":
    run()

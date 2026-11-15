# Focused 30-minute results for the presentation

These figures emphasize the current hybrid's observed strengths. They export frozen results, without changing models, thresholds, labels, campaigns or metric definitions. Each figure has a 300 dpi PNG and a vector PDF.

| Figure | What it supports |
|---|---|
| [01: Timely-warning coverage](01_timely_warning_coverage.png) | The current hybrid warns on 5/8 campaigns (62.5%), versus 3/8 (37.5%) for matched pooled counts and 4/8 for both original versions. |
| [02: Probability error](02_probability_error.png) | The hybrid has the lowest mean 30-minute Brier among these four project versions: 0.001460568. Error is 0.54% lower than matched pooled counts and 4.25% lower than original counts. The matched gain is small. |
| [03: Alarm tradeoff](03_alarm_tradeoff.png) | Extra warning coverage comes with more false episodes than matched counts: 5 versus 1. This is the companion context for the focused figures. |

## Wording supported by the results

> In our exploratory eight-campaign evaluation, the fixed 25% state hybrid achieved higher timely-warning coverage and slightly lower mean probability error at the 30-minute horizon than the matched counts-only model. Coverage increased from 3/8 to 5/8 campaigns, while false-alarm episodes increased from one to five.

Coverage improves by **25 percentage points** relative to matched pooled counts; it improves by **12.5 percentage points** relative to original counts. Neither is a classification-accuracy increase. Avoid calling the result an overall improvement without describing the alarm tradeoff.

## Evaluation and limits

- All four plotted models are project implementations. These figures do not compare complete published systems.
- A timely warning is a **new warning episode starting within 30 minutes before a verified successful-root outcome**. It does not imply prediction before any attack activity or a full 30-minute lead.
- The evaluation uses full AMiner/Suricata/Wazuh inputs, eight held-out AIT campaign folds and no artificially added delay. There is no measured zero-latency guarantee.
- Thresholds were selected on validation under one false episode per 24 negative hours and at most five negative warning minutes. The constraint does not guarantee test alarm rates.
- Brier and average precision are unweighted campaign means. Brier is scaled by 1,000 in the figure; smaller is better. Many negative minutes contribute to its small absolute value.
- Matched pooled counts and the current hybrid use the same calibration procedure. Original counts uses an earlier calibration procedure, so differences against it do not isolate the contribution of stage features.
- Average precision is slightly worse than matched counts: **0.8275 versus 0.8312**. The hybrid is not the winner on every metric.
- This presentation focus and the current preset were chosen after examining the results. All eight campaigns were inspected during development. These are exploratory results, without an independent confirmation or an established statistically significant advantage.
- The 30-minute result does not extend automatically to other horizons. At 15 minutes the hybrid's Brier is worse than both standalone counts variants; complete 15-/30-minute metrics are included in the tables.
- The overall false-episode reduction versus original counts is campaign-dependent. Without wheeler, original counts has two false episodes versus five for the hybrid; frozen thresholds are retained in this sensitivity check.
- CAM transfer remains negative (0/3 timely warnings at both 15 and 30 minutes). These figures do not establish external generalization, prevention effectiveness, or state of the art.
- The successful-root endpoint is a sensitivity rescore of forecasts trained for scheduled escalation.

The Decision Network is an implemented downstream component, but these figures evaluate forecasts, not measured response effectiveness.

## Files and reproduction

`plotted_metrics_30_minutes.csv/json` contains all four metrics, including those the hybrid loses. `all_metrics_15_30_minutes.csv/json` retains both horizons. `campaign_results_30_minutes.csv/json` and `without_wheeler_sensitivity.csv/json` expose campaign-level results. `claim_values.json` stores exact improvements. `manifest.json` records source/output hashes and independent aggregation checks.

Run `python Plots/create_mids_plots.py` from the project root. Sources and further checks are described in [the original results folder](../README.md), [current preset](../../../docs/CURRENT_VERSION.md) and [selective-fusion report](../../../experiments/selective_fusion/REPORT.md).

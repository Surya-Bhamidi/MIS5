# Measured results for presentation

These charts export frozen experimental results; no new fitting or tuning occurs. Every chart is available as a 300 dpi PNG and a vector PDF. CSV and JSON tables preserve exact values.

| Figure | Purpose |
|---|---|
| [01](01_30_minute_comparison.png) | Main 30-minute comparison, including the matched calibration control and original fusion. |
| [02](02_horizon_tradeoffs.png) | All-six-horizon comparison with matched pooled counts. |
| [03](03_campaign_warning_lead_times.png) | Timely warning lead times and missed campaigns. |
| [04](04_campaign_dependence.png) | All campaigns versus removing wheeler, retaining frozen thresholds. |
| [05](05_sensor_availability.png) | Current preset versus matched counts under seven sensor-availability settings. |

The current preset gives **5/8** timely 30-minute warnings versus **4/8** for original counts; Brier is **4.25% lower**, with **5 versus 19** false episodes. Average precision is slightly lower. Matched pooled counts gives 3/8 warnings and one false episode, so the state blend increases both coverage and alarm burden. Original duration/tree fusion gives 4/8 warnings and four false episodes.

Limitations retained: the aggregate false-episode improvement reverses without wheeler; 15-minute probability error is worse than original counts; CAM transfer gives 0/3 timely warnings at both 15 and 30 minutes, with an executed-tactic proxy endpoint and missing AMiner. Response effects are assumed, not physically measured. The preset is a development choice after reviewing previously inspected campaigns, not an independent confirmation. No chart ranks complete published systems.

The successful-root outcome is a sensitivity rescore: forecasting models were trained for scheduled escalation. The alarm budget constrains validation; it does not guarantee a test false-alarm rate. Brier and average precision are unweighted campaign means; warning counts and false episodes are totals.

Sources: [current preset](../../docs/CURRENT_VERSION.md), [selective-fusion report](../../experiments/selective_fusion/REPORT.md), [original comparisons](../../experiments/published_comparison/REPORT.md).

Rebuild from the project root with `python Plots/create_results_plots.py`.

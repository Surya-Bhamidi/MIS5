# Frozen current research preset

Use pooled-calibrated fixed .25 state fusion, with 30-minute warning as the primary use case. All six horizon probabilities use the same blend. BN inference, forward HMM states and the Decision Network remain substantive. Further model development is deferred.

The preset was chosen after reviewing existing test results. It is not a newly confirmed test-selected paper result. See [the current-version specification](../../docs/CURRENT_VERSION.md) and [all comparisons](../selective_fusion/REPORT.md) for the conditional gains and losses.

Prediction archives and validation thresholds are copied exactly; metadata contains the fixed blend calibrators. No fitting or new test campaign occurs during freezing.

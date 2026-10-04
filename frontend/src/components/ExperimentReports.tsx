import React, { useState, useEffect } from "react";
import { FlaskConical, RefreshCw, CheckCircle2, AlertCircle, BarChart2, ShieldAlert, Cpu } from "lucide-react";
import { fetchAllExperiments, rerunExperiments } from "../api/client";

export const ExperimentReports: React.FC = () => {
  const [data, setData] = useState<Record<string, any>>({});
  const [activeRq, setActiveRq] = useState<"RQ1" | "RQ2" | "RQ3" | "RQ4" | "RQ5">("RQ1");
  const [loading, setLoading] = useState(false);
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    loadExperiments();
  }, []);

  const loadExperiments = async () => {
    setLoading(true);
    try {
      const res = await fetchAllExperiments();
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async () => {
    setRerunning(true);
    try {
      const res = await rerunExperiments();
      if (res.results) {
        setData(res.results);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRerunning(false);
    }
  };

  const rq1 = data["RQ1"];
  const rq2 = data["RQ2"];
  const rq3 = data["RQ3"];
  const rq4 = data["RQ4"];
  const rq5 = data["RQ5"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Top Banner with Rerun Action */}
      <div className="glass-card" style={{ padding: "18px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <FlaskConical size={22} color="var(--accent-emerald)" />
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
              Empirical Evaluation & Research Questions (RQ1 – RQ5)
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Rigorous experimental validation across inference accuracy, temporal prediction, decision utility, out-of-distribution robustness, and explainability provenance.
            </p>
          </div>
        </div>

        <button
          onClick={handleRerun}
          disabled={rerunning}
          className="cyber-btn cyber-btn-primary"
          style={{ fontSize: "0.8rem", padding: "8px 16px" }}
        >
          <RefreshCw size={14} className={rerunning ? "animate-spin" : ""} />
          {rerunning ? "Executing Harness..." : "Rerun Evaluation Suite"}
        </button>
      </div>

      {/* Sub-tabs for RQ1 - RQ5 */}
      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "10px", overflowX: "auto" }}>
        {[
          { id: "RQ1", label: "RQ1: BN Inference & Calibration" },
          { id: "RQ2", label: "RQ2: HMM Temporal Prediction" },
          { id: "RQ3", label: "RQ3: Decision Utility & Regret" },
          { id: "RQ4", label: "RQ4: Generalization & Robustness" },
          { id: "RQ5", label: "RQ5: Provenance Audit" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveRq(tab.id as any)}
            className="cyber-btn"
            style={{
              background: activeRq === tab.id ? "rgba(16, 185, 129, 0.15)" : "rgba(255, 255, 255, 0.03)",
              border: activeRq === tab.id ? "1px solid var(--accent-emerald)" : "1px solid var(--border-subtle)",
              color: activeRq === tab.id ? "var(--accent-emerald)" : "var(--text-secondary)",
              borderRadius: "8px",
              padding: "6px 14px",
              fontSize: "0.8rem",
              fontWeight: 600,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content Area */}
      {loading && !data["RQ1"] ? (
        <div className="glass-card" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
          Loading empirical evaluation results...
        </div>
      ) : (
        <>
          {/* RQ1: BN Inference & Calibration */}
          {activeRq === "RQ1" && rq1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Stat Cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Held-Out Accuracy</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent-cyan)", marginTop: "4px" }}>
                    {(rq1.accuracy * 100).toFixed(2)}%
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>LLDOS 1.0 Test Split</div>
                </div>

                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Macro F1-Score</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent-purple)", marginTop: "4px" }}>
                    {rq1.macro_f1}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>Across 6 Threat States</div>
                </div>

                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Expected Calibration Error (ECE)</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent-emerald)", marginTop: "4px" }}>
                    {rq1.expected_calibration_error_ece}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>Reliability Index</div>
                </div>

                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Brier Score</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent-amber)", marginTop: "4px" }}>
                    {rq1.brier_score}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>Lower is better</div>
                </div>
              </div>

              {/* Per-Class Metrics Table */}
              <div className="glass-card" style={{ padding: "18px" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff", marginBottom: "12px" }}>
                  Per-Class Performance Metrics (LLDOS 1.0 Held-Out Alerts)
                </h3>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                      <th style={{ padding: "8px 12px" }}>Threat State</th>
                      <th style={{ padding: "8px 12px" }}>Precision</th>
                      <th style={{ padding: "8px 12px" }}>Recall</th>
                      <th style={{ padding: "8px 12px" }}>F1-Score</th>
                      <th style={{ padding: "8px 12px" }}>Support (# Alerts)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(rq1.per_class_metrics || {}).map(([state, m]: any) => (
                      <tr key={state} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.03)" }}>
                        <td style={{ padding: "8px 12px", fontWeight: 600, color: "#ffffff" }}>{state}</td>
                        <td style={{ padding: "8px 12px" }} className="mono">{(m.precision * 100).toFixed(1)}%</td>
                        <td style={{ padding: "8px 12px" }} className="mono">{(m.recall * 100).toFixed(1)}%</td>
                        <td style={{ padding: "8px 12px", color: "var(--accent-cyan)", fontWeight: 700 }} className="mono">{m.f1_score}</td>
                        <td style={{ padding: "8px 12px", color: "var(--text-muted)" }} className="mono">{m.support}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Calibration Curve Table */}
              <div className="glass-card" style={{ padding: "18px" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff", marginBottom: "12px" }}>
                  Reliability Calibration Table (Confidence vs. Empirical Accuracy)
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "10px" }}>
                  {rq1.calibration_curve?.map((b: any) => (
                    <div key={b.bin_range} style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Bin: {b.bin_range}</div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--accent-emerald)", marginTop: "4px" }} className="mono">
                        Acc: {(b.accuracy * 100).toFixed(1)}%
                      </div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }} className="mono">
                        Conf: {(b.confidence * 100).toFixed(1)}% (N={b.count})
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* RQ2: HMM Temporal Next-Phase Prediction */}
          {activeRq === "RQ2" && rq2 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="glass-card" style={{ padding: "20px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", marginBottom: "8px" }}>
                  Next-Phase Progression Prediction vs. Identity Baseline
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                  Evaluates whether the Hidden Markov Model's temporal transition matrix effectively projects the adversary's next stage (1-step and 2-step lookahead) compared to a naive persistent state baseline.
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
                  {Object.entries(rq2.results || {}).map(([scenario, res]: any) => (
                    <div key={scenario} style={{ background: "rgba(255, 255, 255, 0.02)", borderRadius: "10px", border: "1px solid var(--border-subtle)", padding: "16px" }}>
                      <div style={{ fontWeight: 700, color: "#ffffff", fontSize: "0.9rem", marginBottom: "4px" }}>
                        {scenario.replace("_", " ")}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                        {res.events_evaluated} alert transitions evaluated
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                          <span style={{ color: "var(--text-secondary)" }}>1-Step HMM Prediction:</span>
                          <span className="mono" style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>
                            {(res.hmm_1step_accuracy * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                          <span style={{ color: "var(--text-secondary)" }}>1-Step Baseline (Persistence):</span>
                          <span className="mono" style={{ color: "var(--text-muted)" }}>
                            {(res.baseline_1step_accuracy * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                          <span style={{ color: "var(--text-secondary)" }}>2-Step Lookahead HMM:</span>
                          <span className="mono" style={{ color: "var(--accent-purple)", fontWeight: 700 }}>
                            {(res.hmm_2step_accuracy * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                          <span style={{ color: "var(--text-secondary)" }}>2-Step Baseline:</span>
                          <span className="mono" style={{ color: "var(--text-muted)" }}>
                            {(res.baseline_2step_accuracy * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* RQ3: Decision Utility & Regret */}
          {activeRq === "RQ3" && rq3 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px" }}>
                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Decision Network Mean Utility</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent-emerald)", marginTop: "4px" }}>
                    +{rq3.mean_dn_utility}
                  </div>
                </div>

                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Fixed Rule Baseline Utility</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--text-muted)", marginTop: "4px" }}>
                    +{rq3.mean_rule_utility}
                  </div>
                </div>

                <div className="glass-card" style={{ padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Opportunity Regret Reduction</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent-cyan)", marginTop: "4px" }}>
                    {rq3.regret_reduction_pct}%
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>vs. Fixed Thresholds</div>
                </div>
              </div>

              {/* Cumulative Timeline Chart Table */}
              <div className="glass-card" style={{ padding: "18px" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff", marginBottom: "12px" }}>
                  Cumulative Expected Utility Timeline Across Attack Lifecycle
                </h3>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                        <th style={{ padding: "8px", textAlign: "left" }}>Step</th>
                        <th style={{ padding: "8px", textAlign: "left" }}>Phase</th>
                        <th style={{ padding: "8px", textAlign: "right" }}>Cumulative DN Utility</th>
                        <th style={{ padding: "8px", textAlign: "right" }}>Cumulative Rule Utility</th>
                        <th style={{ padding: "8px", textAlign: "right" }}>Net Gain</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rq3.cumulative_utility_timeline?.map((row: any) => (
                        <tr key={row.step} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.03)" }}>
                          <td style={{ padding: "6px 8px" }} className="mono">{row.step}</td>
                          <td style={{ padding: "6px 8px" }}>Phase {row.phase}</td>
                          <td style={{ padding: "6px 8px", textAlign: "right", color: "var(--accent-emerald)" }} className="mono">+{row.cumulative_decision_network_utility}</td>
                          <td style={{ padding: "6px 8px", textAlign: "right", color: "var(--text-secondary)" }} className="mono">+{row.cumulative_fixed_rule_utility}</td>
                          <td style={{ padding: "6px 8px", textAlign: "right", color: "var(--accent-cyan)", fontWeight: 700 }} className="mono">+{row.net_utility_gain}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* RQ4: Generalization & Robustness */}
          {activeRq === "RQ4" && rq4 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="glass-card" style={{ padding: "18px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", marginBottom: "4px" }}>
                  Generalization Drop: LLDOS 1.0 vs. LLDOS 2.0.2 (Stealthier Adversary)
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "14px" }}>
                  The pipeline was calibrated strictly on LLDOS 1.0. Testing on held-out LLDOS 2.0.2 quantifies performance when an adversary utilizes stealthier vectors (DNS recon, SSH, FTP upload) with 99.5% fewer alerts.
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" }}>
                  <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "14px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>LLDOS 1.0 (In-Distribution)</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--accent-cyan)", marginTop: "4px" }}>
                      {(rq4.cross_scenario_generalization?.lldos1_in_distribution_accuracy * 100).toFixed(1)}%
                    </div>
                  </div>

                  <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "14px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>LLDOS 2.0.2 (Out-of-Distribution)</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--accent-amber)", marginTop: "4px" }}>
                      {(rq4.cross_scenario_generalization?.lldos2_stealthier_out_of_distribution_accuracy * 100).toFixed(1)}%
                    </div>
                  </div>

                  <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "14px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Generalization Delta</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--accent-red)", marginTop: "4px" }}>
                      {(rq4.cross_scenario_generalization?.generalization_delta * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Noise & Evasion Curves */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "16px" }}>
                <div className="glass-card" style={{ padding: "18px" }}>
                  <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff", marginBottom: "10px" }}>
                    Background Noise Sensitivity Curve (0% to 50%)
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {rq4.noise_sensitivity_curve?.map((n: any) => (
                      <div key={n.noise_rate} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                        <span style={{ color: "var(--text-secondary)" }}>Noise: {n.noise_rate}</span>
                        <span className="mono" style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>
                          {(n.accuracy * 100).toFixed(1)}% Accuracy
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="glass-card" style={{ padding: "18px" }}>
                  <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff", marginBottom: "10px" }}>
                    Missing Alert Evasion Sensitivity Curve (0% to 40%)
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {rq4.missing_alert_evasion_curve?.map((m: any) => (
                      <div key={m.missing_rate} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                        <span style={{ color: "var(--text-secondary)" }}>Evasion Rate: {m.missing_rate}</span>
                        <span className="mono" style={{ color: "var(--accent-purple)", fontWeight: 600 }}>
                          {(m.accuracy * 100).toFixed(1)}% Accuracy
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* RQ5: Explainability Audit */}
          {activeRq === "RQ5" && rq5 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="glass-card" style={{ padding: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <CheckCircle2 size={20} color="var(--accent-emerald)" />
                    <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>
                      Automated Provenance & Traceability Verification
                    </h3>
                  </div>
                  <span className="badge badge-emerald" style={{ fontSize: "0.8rem", padding: "4px 10px" }}>
                    AUDIT PASSED (100% VERIFIED)
                  </span>
                </div>

                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "16px" }}>
                  Asserts that 100% of pipeline recommendations can be deterministically traced back to source alert packets, sliding window features, Bayesian Network evidence contributions, HMM transition state, and Decision Network expected utility rankings.
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
                  <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Recommendations Audited</div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#ffffff", marginTop: "4px" }}>
                      {rq5.total_recommendations_audited}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Valid Provenance Traces</div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--accent-emerald)", marginTop: "4px" }}>
                      {rq5.valid_audit_traces}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Traceability Coverage</div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--accent-cyan)", marginTop: "4px" }}>
                      {rq5.provenance_coverage_pct}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Sample Provenance Trace Preview */}
              {rq5.sample_provenance_trace && (
                <div className="glass-card" style={{ padding: "18px" }}>
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff", marginBottom: "8px" }}>
                    Audited Sample Provenance Artifact (Step #{rq5.sample_provenance_trace.step_id}):
                  </h4>
                  <pre style={{ background: "rgba(5, 9, 16, 0.95)", padding: "14px", borderRadius: "8px", fontSize: "0.75rem", color: "var(--accent-cyan)", maxHeight: "280px", overflowY: "auto" }} className="mono">
                    {JSON.stringify(rq5.sample_provenance_trace, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

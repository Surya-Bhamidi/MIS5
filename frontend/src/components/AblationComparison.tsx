import React, { useState, useEffect } from "react";
import { Layers, CheckCircle2, AlertTriangle, ShieldCheck, Zap } from "lucide-react";
import { AblationResult } from "../types";
import { fetchAblationResults } from "../api/client";

interface AblationComparisonProps {
  scenarioId: string;
}

export const AblationComparison: React.FC<AblationComparisonProps> = ({ scenarioId }) => {
  const [data, setData] = useState<AblationResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAblation();
  }, [scenarioId]);

  const loadAblation = async () => {
    setLoading(true);
    try {
      const res = await fetchAblationResults(scenarioId);
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const configs = [
    {
      id: "B0",
      title: "B0: Rule-Based Baseline",
      desc: "Static signature matching & fixed thresholds. Zero probabilistic reasoning or temporal state tracking.",
      accent: "#94a3b8",
      colorClass: "badge-cyan",
    },
    {
      id: "B1",
      title: "B1: BN-Only (Static)",
      desc: "Static Bayesian Network threat-state inference. Estimates state probabilities per alert without temporal kill-chain history.",
      accent: "#60a5fa",
      colorClass: "badge-cyan",
    },
    {
      id: "B2",
      title: "B2: BN + HMM (Heuristic)",
      desc: "Bayesian Network combined with HMM temporal forward filtering. Triggers responses via static probability thresholds.",
      accent: "#f59e0b",
      colorClass: "badge-amber",
    },
    {
      id: "B3",
      title: "B3: Full Pipeline (BN+HMM+DN)",
      desc: "Complete integrated decision-support system. Combines BN evidence, HMM temporal projection, and Decision Network expected utility maximization.",
      accent: "#00f0ff",
      colorClass: "badge-purple",
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Overview Card */}
      <div className="glass-card" style={{ padding: "18px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Layers size={22} color="var(--accent-amber)" />
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
              Pipeline Layer Ablation Study (B0 → B3)
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Side-by-side empirical comparison evaluating the measurable value-add of each architectural layer on the active scenario stream.
            </p>
          </div>
        </div>
      </div>

      {/* Grid of 4 Configurations */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
        {configs.map((c) => {
          const metric = data?.configurations?.[c.id as "B0" | "B1" | "B2" | "B3"];

          return (
            <div
              key={c.id}
              className={`glass-card ${c.id === "B3" ? "glass-card-active" : ""}`}
              style={{ padding: "20px", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: "16px", position: "relative" }}
            >
              {c.id === "B3" ? (
                <div style={{ position: "absolute", top: "12px", right: "12px" }}>
                  <span className="badge badge-cyan" style={{ fontSize: "0.68rem" }}>
                    RECOMMENDED PIPELINE
                  </span>
                </div>
              ) : null}

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                  <Zap size={18} color={c.accent} />
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>
                    {c.title}
                  </h3>
                </div>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                  {c.desc}
                </p>
              </div>

              {/* Metrics Table */}
              <div style={{ background: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid var(--border-subtle)", padding: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Threat State Accuracy:</span>
                  <span className="mono" style={{ color: "#ffffff", fontWeight: 700 }}>
                    {metric ? `${(metric.accuracy * 100).toFixed(1)}%` : "Loading..."}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>False Alarm Rate:</span>
                  <span className="mono" style={{ color: metric && metric.false_alarm_rate > 0.05 ? "var(--accent-red)" : "var(--accent-emerald)", fontWeight: 700 }}>
                    {metric ? `${(metric.false_alarm_rate * 100).toFixed(1)}%` : "Loading..."}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Mean Operational Utility:</span>
                  <span className="mono" style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>
                    {metric ? `${metric.mean_utility > 0 ? "+" : ""}${metric.mean_utility}` : "Loading..."}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Time-to-Detection (TTD):</span>
                  <span className="mono" style={{ color: "var(--accent-purple)", fontWeight: 700 }}>
                    {metric && metric.time_to_detection_steps > 0 ? `Step ${metric.time_to_detection_steps}` : "N/A"}
                  </span>
                </div>
              </div>

              {/* Architectural Characteristics */}
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", borderTop: "1px solid var(--border-subtle)", paddingTop: "10px" }}>
                {c.id === "B0" && "• Lacks uncertainty bounds; fragile against stealthy evasion."}
                {c.id === "B1" && "• Provides probabilistic posteriors, but no sequence memory."}
                {c.id === "B2" && "• Models kill-chain trajectory, but uses rigid heuristics."}
                {c.id === "B3" && "• Optimal balance of false-positive cost vs. attack disruption."}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

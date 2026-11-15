import React from "react";
import { BarChart3 } from "lucide-react";
import { ThreatState } from "../types";

interface BeliefDistributionProps {
  bnBelief: Record<ThreatState, number>;
  hmmBelief: Record<ThreatState, number>;
  activeBelief: Record<ThreatState, number>;
  ablationMode: string;
}

const STATE_COLORS: Record<ThreatState, { bar: string; text: string; bg: string }> = {
  Benign: { bar: "#10b981", text: "#34d399", bg: "rgba(16, 185, 129, 0.15)" },
  Recon: { bar: "#00f0ff", text: "#38bdf8", bg: "rgba(0, 240, 255, 0.15)" },
  Discovery: { bar: "#6366f1", text: "#818cf8", bg: "rgba(99, 102, 241, 0.15)" },
  Compromise: { bar: "#f59e0b", text: "#fbbf24", bg: "rgba(245, 158, 11, 0.15)" },
  PrivEsc: { bar: "#f97316", text: "#fb923c", bg: "rgba(249, 115, 22, 0.15)" },
  ActiveAttack: { bar: "#ef4444", text: "#f87171", bg: "rgba(239, 68, 68, 0.15)" },
};

export const BeliefDistribution: React.FC<BeliefDistributionProps> = ({
  bnBelief,
  hmmBelief,
  activeBelief,
  ablationMode,
}) => {
  const states: ThreatState[] = ["Benign", "Recon", "Discovery", "Compromise", "PrivEsc", "ActiveAttack"];

  // Entropy: H = -sum(p * log2(p))
  const activeProbs = Object.values(activeBelief);
  const entropy = -activeProbs.reduce((acc, p) => (p > 0.001 ? acc + p * Math.log2(p) : acc), 0);

  const topState = states.reduce((prev, curr) =>
    (activeBelief[curr] || 0) > (activeBelief[prev] || 0) ? curr : prev
  );
  const topProb = activeBelief[topState] || 0;

  return (
    <div className="glass-card" style={{ padding: "18px", display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <BarChart3 size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#ffffff" }}>
            Threat-State Belief Distribution
          </h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="badge badge-purple mono" title="Shannon Entropy of current belief distribution">
            Entropy: {entropy.toFixed(2)} bits
          </span>
          <span className="badge badge-cyan mono">
            Mode: {ablationMode}
          </span>
        </div>
      </div>

      {/* Primary Belief Bars */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {states.map((state) => {
          const p = activeBelief[state] || 0;
          const pBn = bnBelief[state] || 0;
          const pHmm = hmmBelief[state] || 0;
          const pct = (p * 100).toFixed(1);
          const colors = STATE_COLORS[state];

          return (
            <div key={state} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                <span style={{ color: colors.text, fontWeight: 600 }}>{state}</span>
                <div style={{ display: "flex", gap: "10px" }}>
                  {ablationMode === "B3" ? (
                    <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }} className="mono">
                      (BN: {(pBn * 100).toFixed(0)}% | HMM: {(pHmm * 100).toFixed(0)}%)
                    </span>
                  ) : null}
                  <span style={{ color: "#ffffff", fontWeight: 700 }} className="mono">
                    {pct}%
                  </span>
                </div>
              </div>

              {/* Progress Bar Container */}
              <div style={{ height: "8px", background: "rgba(255, 255, 255, 0.05)", borderRadius: "4px", overflow: "hidden", position: "relative" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min(100, Math.max(0, p * 100))}%`,
                    background: `linear-gradient(90deg, ${colors.bar}, rgba(255, 255, 255, 0.3))`,
                    borderRadius: "4px",
                    transition: "width 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                    boxShadow: p > 0.3 ? `0 0 10px ${colors.bar}66` : "none",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Diagnostics */}
      <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "12px", display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px", fontSize: "0.78rem" }}>
        <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
          <div style={{ color: "var(--text-muted)" }}>Dominant Threat State</div>
          <div style={{ color: STATE_COLORS[topState]?.text, fontWeight: 700, fontSize: "0.9rem", marginTop: "2px" }}>
            {topState} ({(topProb * 100).toFixed(1)}%)
          </div>
        </div>

        <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
          <div style={{ color: "var(--text-muted)" }}>Inference Certainty</div>
          <div style={{ color: topProb > 0.7 ? "var(--accent-emerald)" : (topProb > 0.4 ? "var(--accent-amber)" : "var(--text-muted)"), fontWeight: 700, fontSize: "0.9rem", marginTop: "2px" }}>
            {topProb > 0.7 ? "HIGH CONFIDENCE" : (topProb > 0.4 ? "MODERATE" : "HIGH UNCERTAINTY")}
          </div>
        </div>
      </div>
    </div>
  );
};

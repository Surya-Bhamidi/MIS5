import React from "react";
import { GitCommit, ArrowRight, Clock } from "lucide-react";
import { ThreatState } from "../types";

interface AttackGraphProps {
  dominantState: ThreatState;
  viterbiPath: ThreatState[];
  projections: Record<ThreatState, number>[];
}

interface PhaseNode {
  key: ThreatState;
  label: string;
  sublabel: string;
  phaseNum: number;
}

const PHASES: PhaseNode[] = [
  { key: "Benign", label: "Normal", sublabel: "Baseline Traffic", phaseNum: 0 },
  { key: "Recon", label: "Phase 1: Recon", sublabel: "IPsweep / Probe", phaseNum: 1 },
  { key: "Discovery", label: "Phase 2: Discovery", sublabel: "Sadmind Ping", phaseNum: 2 },
  { key: "Compromise", label: "Phase 3: Compromise", sublabel: "Sadmind Breakin", phaseNum: 3 },
  { key: "PrivEsc", label: "Phase 4: PrivEsc", sublabel: "Mstream Install", phaseNum: 4 },
  { key: "ActiveAttack", label: "Phase 5: DDoS", sublabel: "mstream Launch", phaseNum: 5 },
];

export const AttackGraph: React.FC<AttackGraphProps> = ({
  dominantState,
  viterbiPath,
  projections,
}) => {
  const currentPhaseIdx = PHASES.findIndex((p) => p.key === dominantState);
  const nextProj = projections.length > 0 ? projections[0] : null;
  const twoStepProj = projections.length > 1 ? projections[1] : null;

  // Find which phase has highest probability at t+1
  const predictedNext = nextProj
    ? (Object.entries(nextProj).reduce((a, b) => (b[1] > a[1] ? b : a))[0] as ThreatState)
    : null;

  return (
    <div className="glass-card" style={{ padding: "18px", display: "flex", flexDirection: "column", gap: "14px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <GitCommit size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#ffffff" }}>
            Kill-Chain Temporal Attack Progression
          </h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Clock size={14} color="var(--accent-cyan)" />
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Next-State Projection Horizon: <strong style={{ color: "var(--accent-cyan)" }}>t+1, t+2</strong>
          </span>
        </div>
      </div>

      {/* Nodes progression pipeline */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative", padding: "10px 0" }}>
        {PHASES.map((phase, idx) => {
          const isActive = phase.key === dominantState;
          const isPassed = viterbiPath.includes(phase.key) || idx <= currentPhaseIdx;
          const isPredictedNext = predictedNext === phase.key;
          const nextProb = nextProj ? (nextProj[phase.key] || 0) * 100 : 0;

          return (
            <React.Fragment key={phase.key}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "6px",
                  zIndex: 2,
                  width: "110px",
                  textAlign: "center",
                }}
              >
                {/* Node Circle */}
                <div
                  style={{
                    width: isActive ? "38px" : "30px",
                    height: isActive ? "38px" : "30px",
                    borderRadius: "50%",
                    background: isActive
                      ? "linear-gradient(135deg, #00f0ff, #a855f7)"
                      : (isPassed ? "rgba(0, 240, 255, 0.2)" : "rgba(255, 255, 255, 0.05)"),
                    border: isActive
                      ? "2px solid #ffffff"
                      : (isPassed ? "1px solid var(--accent-cyan)" : "1px solid var(--border-subtle)"),
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isActive ? "#000000" : (isPassed ? "var(--accent-cyan)" : "var(--text-muted)"),
                    fontWeight: 700,
                    fontSize: "0.8rem",
                    boxShadow: isActive ? "0 0 16px rgba(0, 240, 255, 0.5)" : "none",
                    transition: "all 0.3s ease",
                  }}
                  className={isActive ? "animate-pulse-glow" : ""}
                >
                  {phase.phaseNum}
                </div>

                {/* Node Label */}
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: isActive ? 700 : 500, color: isActive ? "#ffffff" : "var(--text-secondary)" }}>
                    {phase.label}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                    {phase.sublabel}
                  </div>
                </div>

                {/* Forecast projection tag if relevant */}
                {isPredictedNext && !isActive ? (
                  <span className="badge badge-amber mono" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                    Proj: {nextProb.toFixed(0)}%
                  </span>
                ) : null}
              </div>

              {/* Connecting arrow if not last node */}
              {idx < PHASES.length - 1 ? (
                <div
                  style={{
                    flex: 1,
                    height: "2px",
                    background: idx < currentPhaseIdx
                      ? "linear-gradient(90deg, var(--accent-cyan), rgba(0, 240, 255, 0.4))"
                      : "rgba(255, 255, 255, 0.08)",
                    position: "relative",
                    margin: "0 4px",
                    alignSelf: "center",
                    marginBottom: "36px",
                  }}
                >
                  {idx === currentPhaseIdx ? (
                    <div
                      style={{
                        position: "absolute",
                        right: "-4px",
                        top: "-5px",
                        color: "var(--accent-cyan)",
                      }}
                    >
                      <ArrowRight size={12} />
                    </div>
                  ) : null}
                </div>
              ) : null}
            </React.Fragment>
          );
        })}
      </div>

      {/* Viterbi Historical Path summary */}
      <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px 14px", borderRadius: "8px", border: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", fontSize: "0.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ color: "var(--text-muted)" }}>Decoded Viterbi Path:</span>
          <span style={{ color: "var(--accent-cyan)", fontWeight: 600 }} className="mono">
            {viterbiPath.length > 0 ? viterbiPath.slice(-6).join(" → ") : dominantState}
          </span>
        </div>

        {nextProj ? (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "var(--text-muted)" }}>Progression Risk at t+1:</span>
            <span style={{ color: (nextProj["ActiveAttack"] || 0) > 0.3 ? "var(--accent-red)" : "var(--accent-amber)", fontWeight: 700 }} className="mono">
              {(((nextProj["Compromise"] || 0) + (nextProj["PrivEsc"] || 0) + (nextProj["ActiveAttack"] || 0)) * 100).toFixed(1)}% (Escalation Probability)
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
};

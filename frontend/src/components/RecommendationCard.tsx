import React from "react";
import { ShieldAlert, CheckCircle2, Search, ArrowUpRight } from "lucide-react";
import { Recommendation, DefensiveAction } from "../types";

interface RecommendationCardProps {
  recommendation: Recommendation | null;
  onOpenProvenance: () => void;
  onLaunchWhatIf: (action: DefensiveAction) => void;
  ablationMode: string;
}

const ACTION_THEMES: Record<DefensiveAction, { color: string; bg: string; border: string; label: string }> = {
  Monitor: {
    color: "#10b981",
    bg: "rgba(16, 185, 129, 0.15)",
    border: "rgba(16, 185, 129, 0.4)",
    label: "PASSIVE MONITOR",
  },
  Restrict: {
    color: "#00f0ff",
    bg: "rgba(0, 240, 255, 0.15)",
    border: "rgba(0, 240, 255, 0.4)",
    label: "RESTRICT / RATE-LIMIT",
  },
  Block: {
    color: "#f59e0b",
    bg: "rgba(245, 158, 11, 0.15)",
    border: "rgba(245, 158, 11, 0.4)",
    label: "BLOCK INGRESS IP",
  },
  Isolate: {
    color: "#ef4444",
    bg: "rgba(239, 68, 68, 0.18)",
    border: "rgba(239, 68, 68, 0.5)",
    label: "ISOLATE HOST QUARANTINE",
  },
};

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendation,
  onOpenProvenance,
  onLaunchWhatIf,
  ablationMode,
}) => {
  if (!recommendation) {
    return (
      <div className="glass-card" style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)" }}>
        Awaiting incoming alert stream to formulate response recommendation...
      </div>
    );
  }

  const act = recommendation.recommended_action;
  const theme = ACTION_THEMES[act] || ACTION_THEMES.Monitor;

  return (
    <div className="glass-card" style={{ padding: "18px", display: "flex", flexDirection: "column", gap: "14px", position: "relative", overflow: "hidden" }}>
      {/* Top Banner */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ShieldAlert size={18} color={theme.color} />
          <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#ffffff" }}>
            Decision Network Recommendation
          </h3>
        </div>
        <span className="badge badge-cyan mono">
          {ablationMode === "B3" ? "Expected Utility Maximization" : `${ablationMode} Mode`}
        </span>
      </div>

      {/* Main Recommended Action Callout */}
      <div
        style={{
          background: theme.bg,
          border: `1px solid ${theme.border}`,
          borderRadius: "10px",
          padding: "16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
            Recommended Defensive Intervention
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: theme.color, marginTop: "2px", letterSpacing: "-0.01em" }}>
            {theme.label}
          </div>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
            Expected Utility (EU)
          </div>
          <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "#ffffff" }} className="mono">
            {recommendation.expected_utility > 0 ? `+${recommendation.expected_utility}` : recommendation.expected_utility}
          </div>
        </div>
      </div>

      {/* Plain-English Rationale */}
      <div style={{ fontSize: "0.82rem", lineHeight: "1.5", color: "var(--text-secondary)", background: "rgba(255, 255, 255, 0.02)", padding: "12px 14px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
        <div style={{ color: "#ffffff", fontWeight: 600, marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
          <CheckCircle2 size={14} color="var(--accent-cyan)" /> Decision Rationale:
        </div>
        {recommendation.rationale}
      </div>

      {/* Ranked Candidate Responses with Regrets */}
      <div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "8px", fontWeight: 600 }}>
          Ranked Candidate Actions & Opportunity Regrets:
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px" }}>
          {recommendation.ranked_actions.map((ra) => {
            const isOptimal = ra.action === act;
            const rTheme = ACTION_THEMES[ra.action];

            return (
              <div
                key={ra.action}
                style={{
                  background: isOptimal ? rTheme.bg : "rgba(255, 255, 255, 0.02)",
                  border: isOptimal ? `1px solid ${rTheme.border}` : "1px solid var(--border-subtle)",
                  borderRadius: "8px",
                  padding: "8px 10px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 600, color: isOptimal ? rTheme.color : "var(--text-secondary)" }}>
                    {ra.action}
                  </span>
                  {isOptimal ? (
                    <span style={{ fontSize: "0.65rem", color: "var(--accent-cyan)", fontWeight: 700 }}>
                      BEST
                    </span>
                  ) : null}
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "flex", justifyContent: "space-between" }} className="mono">
                  <span>EU: {ra.expected_utility}</span>
                  <span>Regret: {ra.regret}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "8px", borderTop: "1px solid var(--border-subtle)" }}>
        <button
          onClick={onOpenProvenance}
          className="cyber-btn cyber-btn-secondary"
          style={{ fontSize: "0.8rem", padding: "6px 12px" }}
        >
          <Search size={14} /> Explain Recommendation Trace
        </button>

        <button
          onClick={() => onLaunchWhatIf(act)}
          className="cyber-btn cyber-btn-primary"
          style={{ fontSize: "0.8rem", padding: "6px 12px" }}
        >
          <ArrowUpRight size={14} /> Simulate in What-If
        </button>
      </div>
    </div>
  );
};

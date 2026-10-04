import React from "react";
import { Shield, Activity, Cpu, Layers, GitBranch, FlaskConical } from "lucide-react";
import { ScenarioInfo, AblationMode } from "../types";

interface HeaderProps {
  scenarios: ScenarioInfo[];
  selectedScenario: string;
  onSelectScenario: (id: string) => void;
  ablationMode: AblationMode;
  onSelectAblation: (mode: AblationMode) => void;
  activeTab: "console" | "whatif" | "ablation" | "experiments";
  onSelectTab: (tab: "console" | "whatif" | "ablation" | "experiments") => void;
  isStreaming: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  scenarios,
  selectedScenario,
  onSelectScenario,
  ablationMode,
  onSelectAblation,
  activeTab,
  onSelectTab,
  isStreaming,
}) => {
  return (
    <header style={{ borderBottom: "1px solid var(--border-subtle)", background: "rgba(10, 16, 28, 0.85)", backdropFilter: "blur(12px)", position: "sticky", top: 0, zIndex: 100 }}>
      <div style={{ maxWidth: "1600px", margin: "0 auto", padding: "14px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
        
        {/* Brand & Status */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ width: "42px", height: "42px", borderRadius: "10px", background: "linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(168, 85, 247, 0.25))", border: "1px solid rgba(0, 240, 255, 0.4)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Shield size={24} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h1 style={{ fontSize: "1.15rem", fontWeight: 700, letterSpacing: "-0.01em", color: "#ffffff" }}>
                Probabilistic Cyber Threat Progression & Response
              </h1>
              <span className={`badge ${isStreaming ? "badge-emerald animate-pulse-glow" : "badge-cyan"}`}>
                <Activity size={12} />
                {isStreaming ? "LIVE INFERENCE" : "PIPELINE READY"}
              </span>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Transparent Decision Support Pipeline • Bayesian Network + HMM + Decision Network
            </p>
          </div>
        </div>

        {/* Scenario Selector & Ablation Config */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
          {/* Scenario Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 500 }}>Scenario:</span>
            <select
              value={selectedScenario}
              onChange={(e) => onSelectScenario(e.target.value)}
              style={{
                background: "rgba(20, 30, 50, 0.8)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                color: "#ffffff",
                padding: "6px 12px",
                fontSize: "0.82rem",
                outline: "none",
                cursor: "pointer",
              }}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} {s.held_out ? "(Held-Out Test)" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Ablation Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 500 }}>Pipeline Mode:</span>
            <div style={{ display: "inline-flex", background: "rgba(255, 255, 255, 0.04)", padding: "3px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
              {(["B0", "B1", "B2", "B3"] as AblationMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => onSelectAblation(mode)}
                  style={{
                    background: ablationMode === mode ? "linear-gradient(135deg, rgba(0, 240, 255, 0.3), rgba(168, 85, 247, 0.3))" : "transparent",
                    border: ablationMode === mode ? "1px solid var(--accent-cyan)" : "1px solid transparent",
                    borderRadius: "6px",
                    color: ablationMode === mode ? "#ffffff" : "var(--text-secondary)",
                    padding: "4px 10px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  title={
                    mode === "B0" ? "Rule-Based Baseline" :
                    mode === "B1" ? "BN-Only Inference" :
                    mode === "B2" ? "BN + HMM Filter" : "Full BN + HMM + Decision Network"
                  }
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{ maxWidth: "1600px", margin: "0 auto", padding: "0 24px", display: "flex", gap: "8px", borderTop: "1px solid rgba(255, 255, 255, 0.04)" }}>
        <button
          onClick={() => onSelectTab("console")}
          className="cyber-btn"
          style={{
            background: "transparent",
            color: activeTab === "console" ? "var(--accent-cyan)" : "var(--text-secondary)",
            borderBottom: activeTab === "console" ? "2px solid var(--accent-cyan)" : "2px solid transparent",
            borderRadius: "0",
            padding: "10px 16px",
            fontSize: "0.85rem",
          }}
        >
          <Activity size={16} /> Live Analyst Console
        </button>

        <button
          onClick={() => onSelectTab("whatif")}
          className="cyber-btn"
          style={{
            background: "transparent",
            color: activeTab === "whatif" ? "var(--accent-purple)" : "var(--text-secondary)",
            borderBottom: activeTab === "whatif" ? "2px solid var(--accent-purple)" : "2px solid transparent",
            borderRadius: "0",
            padding: "10px 16px",
            fontSize: "0.85rem",
          }}
        >
          <GitBranch size={16} /> What-If Simulator
        </button>

        <button
          onClick={() => onSelectTab("ablation")}
          className="cyber-btn"
          style={{
            background: "transparent",
            color: activeTab === "ablation" ? "var(--accent-amber)" : "var(--text-secondary)",
            borderBottom: activeTab === "ablation" ? "2px solid var(--accent-amber)" : "2px solid transparent",
            borderRadius: "0",
            padding: "10px 16px",
            fontSize: "0.85rem",
          }}
        >
          <Layers size={16} /> Pipeline Ablation (B0→B3)
        </button>

        <button
          onClick={() => onSelectTab("experiments")}
          className="cyber-btn"
          style={{
            background: "transparent",
            color: activeTab === "experiments" ? "var(--accent-emerald)" : "var(--text-secondary)",
            borderBottom: activeTab === "experiments" ? "2px solid var(--accent-emerald)" : "2px solid transparent",
            borderRadius: "0",
            padding: "10px 16px",
            fontSize: "0.85rem",
          }}
        >
          <FlaskConical size={16} /> RQ1-RQ5 Empirical Hub
        </button>
      </div>
    </header>
  );
};

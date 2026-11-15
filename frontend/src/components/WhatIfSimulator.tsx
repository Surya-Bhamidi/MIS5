import React, { useState, useEffect } from "react";
import { GitBranch } from "lucide-react";
import { ThreatState, DefensiveAction, WhatIfResult } from "../types";
import { simulateWhatIf } from "../api/client";

interface WhatIfSimulatorProps {
  currentBelief: Record<ThreatState, number>;
  initialAction?: DefensiveAction;
}

export const WhatIfSimulator: React.FC<WhatIfSimulatorProps> = ({ currentBelief, initialAction = "Isolate" }) => {
  const [selectedAction, setSelectedAction] = useState<DefensiveAction>(initialAction);
  const sourceKey = JSON.stringify(currentBelief);
  const [draft, setDraft] = useState<{ source: string; belief: Record<ThreatState, number> } | null>(null);
  const customBelief = draft?.source === sourceKey ? draft.belief : currentBelief;
  const requestKey = JSON.stringify([selectedAction, customBelief]);
  const [response, setResponse] = useState<{ key: string; result: WhatIfResult } | null>(null);
  const [error, setError] = useState<{ key: string; message: string } | null>(null);
  const simResult = response?.key === requestKey ? response.result : null;
  const currentError = error?.key === requestKey ? error.message : null;

  useEffect(() => {
    let active = true;
    const [action, belief] = JSON.parse(requestKey) as [DefensiveAction, Record<ThreatState, number>];
    simulateWhatIf(belief, action, "Monitor").then(result => {
      if (active) { setResponse({ key: requestKey, result }); setError(null); }
    }).catch(() => {
      if (active) setError({ key: requestKey, message: "The illustrative simulation could not be calculated." });
    });
    return () => { active = false; };
  }, [requestKey]);

  const handleSliderChange = (state: ThreatState, val: number) => {
    const updated = { ...customBelief, [state]: val / 100 };
    // Normalize sum to 1
    const total = Object.values(updated).reduce((a, b) => a + b, 0);
    if (total <= 0) return;
    const normalized: any = {};
    for (const [k, v] of Object.entries(updated)) {
      normalized[k] = total > 0 ? v / total : 0;
    }
    setDraft({ source: sourceKey, belief: normalized });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Title & Introduction */}
      <div className="glass-card" style={{ padding: "18px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <GitBranch size={22} color="var(--accent-purple)" />
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
              Illustrative What-If Simulator
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Compare modeled losses under assumed action effects. No defense is executed, and actual prevention or financial savings are not measured.
            </p>
          </div>
        </div>
      </div>

      {/* Main Grid: Control Panel + Simulation Output */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "20px" }}>
        
        {/* Left Column: Interventions & Belief Controls */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          
          {/* Action Selection */}
          <div className="glass-card" style={{ padding: "18px" }}>
            <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff", marginBottom: "12px" }}>
              1. Choose Hypothetical Action
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
              {(["Monitor", "Restrict", "Block", "Isolate"] as DefensiveAction[]).map((act) => {
                const isSelected = selectedAction === act;
                return (
                  <button
                    key={act}
                    onClick={() => setSelectedAction(act)}
                    className="cyber-btn"
                    style={{
                      padding: "12px",
                      borderRadius: "8px",
                      background: isSelected ? "linear-gradient(135deg, rgba(168, 85, 247, 0.3), rgba(0, 240, 255, 0.2))" : "rgba(255, 255, 255, 0.03)",
                      border: isSelected ? "1px solid var(--accent-purple)" : "1px solid var(--border-subtle)",
                      color: isSelected ? "#ffffff" : "var(--text-secondary)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      gap: "4px",
                    }}
                  >
                    <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>{act}</span>
                    <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                      {act === "Monitor" ? "Passive telemetry" : act === "Restrict" ? "Rate-limit RPC/scan" : act === "Block" ? "Drop ingress IP" : "Quarantine host"}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Belief Sliders */}
          <div className="glass-card" style={{ padding: "18px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff" }}>
                2. Synthetic Belief Sliders
              </h3>
              <button
                onClick={() => {
                  setDraft(null);
                }}
                className="cyber-btn cyber-btn-secondary"
                style={{ fontSize: "0.7rem", padding: "3px 8px" }}
              >
                Reset to Observed Belief
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {(Object.keys(customBelief) as ThreatState[]).map((state) => {
                const val = Math.round((customBelief[state] || 0) * 100);
                return (
                  <div key={state} style={{ fontSize: "0.78rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
                      <span style={{ color: "var(--text-secondary)" }}>{state}</span>
                      <span className="mono" style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>{val}%</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={val}
                      onChange={(e) => handleSliderChange(state, parseInt(e.target.value))}
                      style={{ width: "100%", accentColor: "var(--accent-purple)", cursor: "pointer" }}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Comparative Trajectory & Cost Curves */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {simResult ? (
            <>
              {/* Stat Badges */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
                <div className="glass-card" style={{ padding: "14px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Assumed Mitigation</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--accent-emerald)", marginTop: "4px" }}>
                    {simResult.threat_mitigation_rate}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>Model assumption, not measured</div>
                </div>

                <div className="glass-card" style={{ padding: "14px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Expected Utility Gain</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--accent-cyan)", marginTop: "4px" }}>
                    {simResult.utility_delta > 0 ? `+${simResult.utility_delta}` : simResult.utility_delta}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>vs. Passive Monitor</div>
                </div>

                <div className="glass-card" style={{ padding: "14px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Modeled Loss Difference</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--accent-purple)", marginTop: "4px" }}>
                    {simResult.net_loss_prevented}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>Model units over 5 steps</div>
                </div>
              </div>

              {/* Trajectory Comparison Chart */}
              <div className="glass-card" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff" }}>
                    5-Step Cumulative Loss Projection Horizon
                  </h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "0.75rem" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "var(--accent-purple)" }}>
                      ● With {selectedAction}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "var(--accent-red)" }}>
                      ● Baseline (Monitor)
                    </span>
                  </div>
                </div>

                {/* SVG Line / Bar Chart */}
                <div style={{ height: "240px", width: "100%", position: "relative", display: "flex", alignItems: "flex-end", gap: "20px", padding: "20px 10px 10px 10px", borderBottom: "1px solid var(--border-subtle)" }}>
                  {simResult.loss_trajectories.baseline.map((base, idx) => {
                    const hypo = simResult.loss_trajectories.hypothetical[idx];
                    const maxLoss = Math.max(
                      ...simResult.loss_trajectories.baseline.map((b) => b.cumulative_loss),
                      ...simResult.loss_trajectories.hypothetical.map((b) => b.cumulative_loss),
                      1
                    );

                    const baseHeight = (base.cumulative_loss / maxLoss) * 100;
                    const hypoHeight = (hypo.cumulative_loss / maxLoss) * 100;

                    return (
                      <div key={base.step} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", height: "100%", justifyContent: "flex-end" }}>
                        <div style={{ display: "flex", alignItems: "flex-end", gap: "6px", width: "100%", justifyContent: "center", height: "100%" }}>
                          {/* Hypothetical Bar */}
                          <div
                            style={{
                              width: "35%",
                              height: `${hypoHeight}%`,
                              background: "linear-gradient(180deg, var(--accent-purple), rgba(168, 85, 247, 0.4))",
                              borderRadius: "4px 4px 0 0",
                              transition: "height 0.4s ease",
                            }}
                            title={`Step ${base.step} With ${selectedAction}: ${hypo.cumulative_loss} model units`}
                          />
                          {/* Baseline Bar */}
                          <div
                            style={{
                              width: "35%",
                              height: `${baseHeight}%`,
                              background: "linear-gradient(180deg, var(--accent-red), rgba(239, 68, 68, 0.4))",
                              borderRadius: "4px 4px 0 0",
                              transition: "height 0.4s ease",
                            }}
                            title={`Step ${base.step} Baseline (Monitor): ${base.cumulative_loss} model units`}
                          />
                        </div>
                        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                          t+{base.step}
                        </span>
                      </div>
                    );
                  })}
                </div>

                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                  <strong style={{ color: "#ffffff" }}>Illustrative assumptions:</strong> The configured effectiveness for <span style={{ color: "var(--accent-purple)", fontWeight: 600 }}>{selectedAction}</span> maps the modeled threat mass from {(simResult.original_threat_mass * 100).toFixed(1)}% to {(simResult.residual_threat_mass * 100).toFixed(1)}%. The projected loss difference is {simResult.net_loss_prevented} model units. No defense was executed, and no actual prevention or financial saving was measured.
                </div>
              </div>
            </>
          ) : (
            <div className="glass-card" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
              {currentError || "Running illustrative projection..."}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

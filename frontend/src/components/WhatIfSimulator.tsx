import React, { useState, useEffect } from "react";
import { GitBranch, Shield, AlertTriangle, TrendingDown, ArrowRight, DollarSign } from "lucide-react";
import { ThreatState, DefensiveAction, WhatIfResult } from "../types";
import { simulateWhatIf } from "../api/client";

interface WhatIfSimulatorProps {
  currentBelief: Record<ThreatState, number>;
}

export const WhatIfSimulator: React.FC<WhatIfSimulatorProps> = ({ currentBelief }) => {
  const [selectedAction, setSelectedAction] = useState<DefensiveAction>("Isolate");
  const [simResult, setSimResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [customBelief, setCustomBelief] = useState<Record<ThreatState, number>>({ ...currentBelief });

  useEffect(() => {
    setCustomBelief({ ...currentBelief });
  }, [currentBelief]);

  useEffect(() => {
    runSimulation(selectedAction, customBelief);
  }, [selectedAction]);

  const runSimulation = async (action: DefensiveAction, belief: Record<ThreatState, number>) => {
    setLoading(true);
    try {
      const res = await simulateWhatIf(belief, action, "Monitor");
      setSimResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSliderChange = (state: ThreatState, val: number) => {
    const updated = { ...customBelief, [state]: val / 100 };
    // Normalize sum to 1
    const total = Object.values(updated).reduce((a, b) => a + b, 0);
    const normalized: any = {};
    for (const [k, v] of Object.entries(updated)) {
      normalized[k] = total > 0 ? v / total : 0;
    }
    setCustomBelief(normalized);
    runSimulation(selectedAction, normalized);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Title & Introduction */}
      <div className="glass-card" style={{ padding: "18px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <GitBranch size={22} color="var(--accent-purple)" />
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
              What-If Counterfactual Defensive Simulator
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Simulate hypothetical interventions against internal probabilistic models. Compare future projected loss trajectories and risk reduction vs. a passive monitoring baseline.
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
                  setCustomBelief({ ...currentBelief });
                  runSimulation(selectedAction, currentBelief);
                }}
                className="cyber-btn cyber-btn-secondary"
                style={{ fontSize: "0.7rem", padding: "3px 8px" }}
              >
                Reset to Live
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
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Threat Mitigation</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--accent-emerald)", marginTop: "4px" }}>
                    {simResult.threat_mitigation_rate}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>Progression Arrested</div>
                </div>

                <div className="glass-card" style={{ padding: "14px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Expected Utility Gain</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--accent-cyan)", marginTop: "4px" }}>
                    {simResult.utility_delta > 0 ? `+${simResult.utility_delta}` : simResult.utility_delta}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>vs. Passive Monitor</div>
                </div>

                <div className="glass-card" style={{ padding: "14px", textAlign: "center" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Net Loss Prevented</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--accent-purple)", marginTop: "4px" }}>
                    ${simResult.net_loss_prevented}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>5-Step Projected Savings</div>
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
                      100
                    );

                    const baseHeight = Math.min(100, Math.max(10, (base.cumulative_loss / maxLoss) * 100));
                    const hypoHeight = Math.min(100, Math.max(5, (hypo.cumulative_loss / maxLoss) * 100));

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
                            title={`Step ${base.step} With ${selectedAction}: $${hypo.cumulative_loss}`}
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
                            title={`Step ${base.step} Baseline (No Action): $${base.cumulative_loss}`}
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
                  <strong style={{ color: "#ffffff" }}>Key Insight:</strong> Executing <span style={{ color: "var(--accent-purple)", fontWeight: 600 }}>{selectedAction}</span> reduces the unmitigated attack progression probability from <span className="mono" style={{ color: "var(--accent-red)" }}>{(simResult.original_threat_mass * 100).toFixed(1)}%</span> down to <span className="mono" style={{ color: "var(--accent-emerald)" }}>{(simResult.residual_threat_mass * 100).toFixed(1)}%</span>, resulting in a net projected risk reduction of <span className="mono" style={{ color: "var(--accent-emerald)", fontWeight: 700 }}>${simResult.net_loss_prevented}</span> over the next 5 kill-chain steps.
                </div>
              </div>
            </>
          ) : (
            <div className="glass-card" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
              Running counterfactual projection...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

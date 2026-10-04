import React, { useState } from "react";
import { X, Search, CheckCircle, Database, GitBranch, Cpu, Code, Copy, Check } from "lucide-react";
import { ProvenanceTrace } from "../types";

interface ExplainabilityModalProps {
  trace: ProvenanceTrace | null;
  onClose: () => void;
}

export const ExplainabilityModal: React.FC<ExplainabilityModalProps> = ({ trace, onClose }) => {
  const [activeSubtab, setActiveSubtab] = useState<"provenance" | "json">("provenance");
  const [copied, setCopied] = useState(false);

  if (!trace) return null;

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(trace, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(3, 7, 18, 0.85)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        className="glass-card"
        style={{
          width: "100%",
          maxWidth: "850px",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          border: "1px solid rgba(0, 240, 255, 0.3)",
          boxShadow: "0 0 40px rgba(0, 240, 255, 0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Search size={20} color="var(--accent-cyan)" />
            <div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff" }}>
                Deep Explainability & Provenance Trace
              </h2>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Step #{trace.step_id} • Pipeline Mode: {trace.ablation_mode} • Decision: {trace.decision_network_evaluation?.chosen_action}
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ display: "flex", background: "rgba(255, 255, 255, 0.04)", padding: "2px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <button
                onClick={() => setActiveSubtab("provenance")}
                style={{
                  background: activeSubtab === "provenance" ? "rgba(0, 240, 255, 0.2)" : "transparent",
                  color: activeSubtab === "provenance" ? "#ffffff" : "var(--text-muted)",
                  border: "none",
                  padding: "4px 10px",
                  borderRadius: "4px",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                Visual Trace
              </button>
              <button
                onClick={() => setActiveSubtab("json")}
                style={{
                  background: activeSubtab === "json" ? "rgba(0, 240, 255, 0.2)" : "transparent",
                  color: activeSubtab === "json" ? "#ffffff" : "var(--text-muted)",
                  border: "none",
                  padding: "4px 10px",
                  borderRadius: "4px",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                Raw JSON
              </button>
            </div>

            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-secondary)",
                cursor: "pointer",
                padding: "4px",
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "18px" }}>
          {activeSubtab === "json" ? (
            <div style={{ position: "relative" }}>
              <button
                onClick={handleCopyJson}
                className="cyber-btn cyber-btn-secondary"
                style={{ position: "absolute", top: "10px", right: "10px", fontSize: "0.75rem", padding: "4px 8px" }}
              >
                {copied ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy JSON"}
              </button>
              <pre
                style={{
                  background: "rgba(5, 9, 16, 0.95)",
                  padding: "16px",
                  borderRadius: "8px",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "0.75rem",
                  color: "var(--accent-cyan)",
                  overflowX: "auto",
                  maxHeight: "550px",
                }}
                className="mono"
              >
                {JSON.stringify(trace, null, 2)}
              </pre>
            </div>
          ) : (
            <>
              {/* Provenance Step 1: Raw Alert Ingestion */}
              <div style={{ background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--border-subtle)", borderRadius: "10px", padding: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <Database size={16} color="var(--accent-cyan)" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                    1. Triggering Alert & Sensor Observation
                  </h4>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "10px", fontSize: "0.78rem" }} className="mono">
                  <div><span style={{ color: "var(--text-muted)" }}>Source:</span> {trace.raw_alert?.src_ip}:{trace.raw_alert?.src_port}</div>
                  <div><span style={{ color: "var(--text-muted)" }}>Target:</span> {trace.raw_alert?.dst_ip}:{trace.raw_alert?.dst_port}</div>
                  <div><span style={{ color: "var(--text-muted)" }}>Service:</span> {trace.raw_alert?.service_name}</div>
                  <div><span style={{ color: "var(--text-muted)" }}>Sensor:</span> {trace.raw_alert?.sensor_source?.toUpperCase()} {trace.raw_alert?.session_cooccurred ? "(Dual-Sensor Corroborated)" : ""}</div>
                </div>
              </div>

              {/* Provenance Step 2: Bayesian Network Attribution */}
              <div style={{ background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--border-subtle)", borderRadius: "10px", padding: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <Cpu size={16} color="var(--accent-purple)" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                    2. Bayesian Network Evidence Log-Likelihood Ratios
                  </h4>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {Object.entries(trace.bn_attributions || {}).map(([feature, attr]) => (
                    <div
                      key={feature}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "6px 10px",
                        background: "rgba(255, 255, 255, 0.02)",
                        borderRadius: "6px",
                        fontSize: "0.78rem",
                      }}
                    >
                      <div>
                        <strong style={{ color: "var(--text-primary)" }}>{feature}:</strong>{" "}
                        <span style={{ color: "var(--accent-cyan)" }} className="mono">{attr.value}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }} className="mono">
                        <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>
                          Weight: {attr.log_evidence_weight > 0 ? `+${attr.log_evidence_weight}` : attr.log_evidence_weight}
                        </span>
                        <span className={`badge ${attr.favors_top_state ? "badge-emerald" : "badge-red"}`} style={{ fontSize: "0.68rem" }}>
                          {attr.favors_top_state ? "FAVORS THREAT" : "DISFAVORS"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Provenance Step 3: HMM Temporal Transition */}
              <div style={{ background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--border-subtle)", borderRadius: "10px", padding: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <GitBranch size={16} color="var(--accent-amber)" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                    3. Temporal Kill-Chain Progression (HMM)
                  </h4>
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                  <div>
                    Prior State: <strong style={{ color: "#ffffff" }}>{trace.hmm_transition?.prior_dominant_state}</strong> • Transition Likelihood: <strong className="mono" style={{ color: "var(--accent-cyan)" }}>{trace.hmm_transition?.evidence_probability}</strong>
                  </div>
                  <div style={{ marginTop: "4px" }}>
                    Recent Viterbi Sequence:{" "}
                    <span className="mono" style={{ color: "var(--accent-cyan)" }}>
                      {trace.hmm_transition?.viterbi_recent_path?.join(" → ")}
                    </span>
                  </div>
                </div>
              </div>

              {/* Provenance Step 4: Decision Network Trade-offs */}
              <div style={{ background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--border-subtle)", borderRadius: "10px", padding: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <CheckCircle size={16} color="var(--accent-emerald)" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                    4. Decision Network Expected Utility Maximization
                  </h4>
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
                  {trace.rationale}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "8px" }}>
                  {trace.decision_network_evaluation?.ranked_actions?.map((r) => (
                    <div
                      key={r.action}
                      style={{
                        padding: "8px",
                        background: r.action === trace.decision_network_evaluation?.chosen_action ? "rgba(0, 240, 255, 0.15)" : "rgba(255, 255, 255, 0.02)",
                        border: r.action === trace.decision_network_evaluation?.chosen_action ? "1px solid var(--accent-cyan)" : "1px solid var(--border-subtle)",
                        borderRadius: "6px",
                        fontSize: "0.75rem",
                      }}
                    >
                      <div style={{ fontWeight: 600, color: "#ffffff" }}>{r.action}</div>
                      <div className="mono" style={{ color: "var(--text-muted)", fontSize: "0.7rem", marginTop: "2px" }}>
                        EU: {r.expected_utility} | Regret: {r.regret}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

import React from "react";
import { Play, Pause, StepForward, RotateCcw, Radio } from "lucide-react";
import { AlertEvent } from "../types";

interface LiveFeedProps {
  alerts: AlertEvent[];
  currentIndex: number;
  isStreaming: boolean;
  onToggleStreaming: () => void;
  onStepForward: () => void;
  onReset: () => void;
  speed: number;
  onChangeSpeed: (s: number) => void;
  onSelectAlert: (index: number) => void;
  loading: boolean;
}

export const LiveFeed: React.FC<LiveFeedProps> = ({
  alerts,
  currentIndex,
  isStreaming,
  onToggleStreaming,
  onStepForward,
  onReset,
  speed,
  onChangeSpeed,
  onSelectAlert,
  loading,
}) => {

  return (
    <div className="glass-card" style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Controls Bar */}
      <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Radio size={18} color="var(--accent-cyan)" />
          <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#ffffff" }}>Archived Alert Replay</span>
          <span className="badge badge-cyan mono">
            {alerts.length > 0 ? `${currentIndex + 1} / ${alerts.length}` : "0 / 0"}
          </span>
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={onToggleStreaming}
            disabled={loading || alerts.length === 0}
            className={`cyber-btn ${isStreaming ? "cyber-btn-secondary" : "cyber-btn-primary"}`}
            style={{ padding: "6px 14px" }}
          >
            {isStreaming ? <Pause size={14} /> : <Play size={14} />}
            {isStreaming ? "Pause" : "Play"}
          </button>

          <button
            onClick={onStepForward}
            disabled={loading || isStreaming || currentIndex >= alerts.length - 1}
            className="cyber-btn cyber-btn-secondary"
            style={{ padding: "6px 12px" }}
            title="Step next alert"
          >
            <StepForward size={14} /> Step
          </button>

          <button
            onClick={onReset}
            disabled={loading}
            className="cyber-btn cyber-btn-secondary"
            style={{ padding: "6px 10px" }}
            title="Reset stream"
          >
            <RotateCcw size={14} />
          </button>

          {/* Speed Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px", marginLeft: "6px" }}>
            {[1, 2, 5].map((s) => (
              <button
                key={s}
                onClick={() => onChangeSpeed(s)}
                style={{
                  background: speed === s ? "rgba(0, 240, 255, 0.2)" : "rgba(255, 255, 255, 0.04)",
                  border: speed === s ? "1px solid var(--accent-cyan)" : "1px solid var(--border-subtle)",
                  color: speed === s ? "#ffffff" : "var(--text-muted)",
                  padding: "4px 8px",
                  borderRadius: "6px",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Alert Feed Table */}
      <div style={{ flex: 1, overflowY: "auto", maxHeight: "380px" }}>
        {alerts.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--text-muted)" }}>
            {loading ? "Ingesting alerts from SQLite..." : "No alerts found for this scenario."}
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", textAlign: "left" }}>
            <thead>
              <tr style={{ background: "rgba(10, 16, 28, 0.95)", borderBottom: "1px solid var(--border-subtle)", position: "sticky", top: 0, zIndex: 10 }}>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>#</th>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>Time</th>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>Sensor</th>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>Source IP:Port</th>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>Destination IP:Port</th>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>Signature / Service</th>
                <th style={{ padding: "8px 12px", color: "var(--text-muted)" }}>True Phase</th>
              </tr>
            </thead>
            <tbody>
              {alerts.slice(Math.max(0, currentIndex - 25), currentIndex + 15).map((a, idx) => {
                const actualIdx = Math.max(0, currentIndex - 25) + idx;
                const isSelected = actualIdx === currentIndex;

                return (
                  <tr
                    key={a.id || actualIdx}
                    onClick={() => onSelectAlert(actualIdx)}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.03)",
                      background: isSelected ? "rgba(0, 240, 255, 0.12)" : "transparent",
                      cursor: "pointer",
                      transition: "background 0.15s ease",
                    }}
                  >
                    <td style={{ padding: "6px 12px", color: isSelected ? "var(--accent-cyan)" : "var(--text-muted)", fontWeight: isSelected ? 700 : 400 }} className="mono">
                      {actualIdx + 1}
                    </td>
                    <td style={{ padding: "6px 12px", color: "var(--text-secondary)" }} className="mono">
                      {a.timestamp_iso ? a.timestamp_iso.split("T")[1]?.slice(0, 8) : "--:--:--"}
                    </td>
                    <td style={{ padding: "6px 12px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span className={`badge ${a.sensor_source === "dmz" ? "badge-purple" : "badge-cyan"}`}>
                          {a.sensor_source.toUpperCase()}
                        </span>
                        {a.session_cooccurred ? (
                          <span className="badge badge-amber" title="Observed simultaneously by Inside and DMZ sensors">
                            DUAL
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td style={{ padding: "6px 12px", color: "var(--text-primary)" }} className="mono">
                      {a.src_ip}:{a.src_port || "*"}
                    </td>
                    <td style={{ padding: "6px 12px", color: "var(--text-primary)" }} className="mono">
                      {a.dst_ip}:{a.dst_port || "*"}
                    </td>
                    <td style={{ padding: "6px 12px", color: "var(--accent-cyan)" }}>
                      <span className="mono" style={{ fontSize: "0.75rem" }}>
                        {a.signature_category} ({a.service_name || "net"})
                      </span>
                    </td>
                    <td style={{ padding: "6px 12px" }}>
                      <span className={`badge ${
                        a.true_phase_label === 0 ? "badge-emerald" :
                        a.true_phase_label <= 2 ? "badge-cyan" :
                        a.true_phase_label <= 4 ? "badge-amber" : "badge-red"
                      }`}>
                        Phase {a.true_phase_label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

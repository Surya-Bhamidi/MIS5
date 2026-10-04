from typing import List, Dict, Any
from collections import defaultdict

def classify_signature(service_name: str, dport: str, true_phase: int = 0) -> str:
    """
    Maps observed protocol/service and port to a signature category.
    true_phase is retained for call compatibility, never used as evidence.
    """
    svc = (service_name or "").lower()
    port = str(dport or "").strip()
    p = int(port) if port.isdigit() else 0

    if "icmp" in svc or p == 0:
        return "ICMP_SWEEP"
    if "dns" in svc or p == 53:
        return "ICMP_SWEEP"  # Recon category
    if p == 111 or (32768 <= p <= 34500) or p == 54791 or "rpc" in svc or "sadmind" in svc:
        if "breakin" in svc or "exploit" in svc:
            return "EXPLOIT_PAYLOAD"
        return "RPC_DISCOVERY"
    if "ftp" in svc or p in [20, 21]:
        return "EXPLOIT_PAYLOAD"
    if p in [22, 23, 514] or "telnet" in svc or "ssh" in svc or "rsh" in svc:
        return "REMOTE_SHELL"
    if p in [9325, 7983] or "flood" in svc:
        return "DDOS_FLOOD"

    return "BENIGN_ROUTINE"

def classify_port(dport: str) -> str:
    if not dport or not str(dport).isdigit():
        return "STANDARD"
    p = int(dport)
    if p in [20, 21, 22, 23, 25, 53, 80, 443]:
        return "STANDARD"
    if p == 111 or (32768 <= p <= 34500) or p == 54791:
        return "RPC_HIGH"
    return "FLOOD_EPHEMERAL"

class EventNormalizer:
    """
    Normalizes raw parsed alerts into common schema and merges Inside & DMZ streams
    with dual-sensor session co-occurrence tagging.
    """

    @staticmethod
    def normalize_and_merge(alerts: List[Dict[str, Any]], cooccur_window_sec: float = 3.0) -> List[Dict[str, Any]]:
        if not alerts:
            return []

        # Sort primarily by timestamp, then alert_id
        sorted_alerts = sorted(alerts, key=lambda a: (a["timestamp"], a.get("alert_id", "")))

        # Only prior reports may corroborate the current report. Do not revise
        # an earlier event because a later sensor report was present in a file.
        last_seen = defaultdict(dict)
        cooccurred_indices = set()
        for idx, a in enumerate(sorted_alerts):
            key = (a["src_ip"], a["dst_ip"])
            ts, sensor = a["timestamp"], a["sensor_source"]
            opposite = "inside" if sensor == "dmz" else "dmz"
            prior_ts = last_seen[key].get(opposite)
            if prior_ts is not None and 0 <= ts - prior_ts <= cooccur_window_sec:
                cooccurred_indices.add(idx)
            last_seen[key][sensor] = ts

        normalized: List[Dict[str, Any]] = []
        for i, a in enumerate(sorted_alerts):
            sig_cat = classify_signature(a["service_name"], a["dst_port"])
            port_cls = classify_port(a["dst_port"])
            is_cooccur = i in cooccurred_indices

            norm_event = {
                "id": i + 1,
                "timestamp": a["timestamp"],
                "timestamp_iso": a["timestamp_iso"],
                "src_ip": a["src_ip"],
                "src_port": a["src_port"],
                "dst_ip": a["dst_ip"],
                "dst_port": a["dst_port"],
                "service_name": a["service_name"],
                "alert_type": sig_cat,
                "signature_category": sig_cat,
                "port_class": port_cls,
                "sensor_source": a["sensor_source"],
                "session_cooccurred": 1 if is_cooccur else 0,
                "sensor_corroboration": "DUAL_SENSOR" if is_cooccur else "SINGLE_SENSOR",
                "true_phase_label": a["true_phase_label"],
                "source_file": a.get("source_file", ""),
            }
            normalized.append(norm_event)

        return normalized

    @staticmethod
    def extract_window_features(recent_events: List[Dict[str, Any]], current_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derives discrete evidence features over a sliding window ending at current_event.
        """
        all_events = recent_events + [current_event] if current_event not in recent_events else recent_events
        cur_ts = current_event.get("timestamp", 0.0)
        all_events = [e for e in all_events if e.get("timestamp", 0.0) <= cur_ts]
        unique_targets = {e["dst_ip"] for e in all_events if e.get("dst_ip")}
        target_div = "MULTI_HOST" if len(unique_targets) > 2 else "SINGLE_HOST"

        # Rate: events in the last 60 seconds
        recent_60s = [e for e in all_events if 0 <= cur_ts - e.get("timestamp", 0.0) <= 60.0]
        count_60s = len(recent_60s)
        if count_60s <= 5:
            rate_cat = "LOW"
        elif count_60s <= 25:
            rate_cat = "MEDIUM"
        else:
            rate_cat = "HIGH"

        return {
            "signature_category": current_event.get("signature_category", "BENIGN_ROUTINE"),
            "target_diversity": target_div,
            "port_class": current_event.get("port_class", "STANDARD"),
            "sensor_corroboration": current_event.get("sensor_corroboration", "SINGLE_SENSOR"),
            "alert_rate": rate_cat,
        }

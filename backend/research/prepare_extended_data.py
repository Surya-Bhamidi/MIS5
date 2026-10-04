"""Read archive streams into separate research features; no archive extraction."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import struct
import tarfile
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import evidence_pilot as pilot

ROOT = pilot.ROOT
OUT = ROOT / "data" / "research" / "extended"
PACKET_NAMES = ["packets", "bytes", "tcp_syn", "tcp_ack", "tcp_rst", "udp", "icmp_echo",
                "dns", "dns_hinfo", "rpc", "remote_shell", "ftp", "mstream_control",
                "unique_sources", "unique_targets", "unique_destination_ports"]


def pcap_records(stream):
    header = stream.read(24)
    if len(header) != 24:
        raise ValueError("Truncated PCAP header")
    magic = header[:4]
    formats = {b"\xa1\xb2\xc3\xd4": (">", 1e6), b"\xd4\xc3\xb2\xa1": ("<", 1e6),
               b"\xa1\xb2\x3c\x4d": (">", 1e9), b"\x4d\x3c\xb2\xa1": ("<", 1e9)}
    if magic not in formats:
        raise ValueError("Unsupported PCAP magic")
    order, scale = formats[magic]
    link = struct.unpack(order + "I", header[20:24])[0]
    if link != 1:
        raise ValueError(f"Expected Ethernet, found link type {link}")
    unpack = struct.Struct(order + "IIII").unpack
    while True:
        h = stream.read(16)
        if not h:
            return
        if len(h) != 16:
            raise ValueError("Truncated packet header")
        sec, fraction, captured, original = unpack(h)
        if captured > 16 * 1024 * 1024:
            raise ValueError("Unreasonable captured length")
        packet = stream.read(captured)
        if len(packet) != captured:
            raise ValueError("Truncated packet data")
        yield sec + fraction / scale, original, packet


def ipv4(packet):
    if len(packet) < 34:
        return None
    offset = 14
    ether = int.from_bytes(packet[12:14], "big")
    while ether in [0x8100, 0x88a8] and len(packet) >= offset + 4:
        ether = int.from_bytes(packet[offset + 2:offset + 4], "big")
        offset += 4
    if ether != 0x800 or len(packet) < offset + 20:
        return None
    ip = packet[offset:]
    ihl = (ip[0] & 15) * 4
    if ip[0] >> 4 != 4 or ihl < 20 or len(ip) < ihl:
        return None
    fragment = int.from_bytes(ip[6:8], "big") & 0x1fff
    protocol, source, target = ip[9], ip[12:16], ip[16:20]
    payload = ip[ihl:]
    sport = dport = 0
    if protocol in [6, 17] and fragment == 0 and len(payload) >= 4:
        sport, dport = struct.unpack(">HH", payload[:4])
    return protocol, source, target, sport, dport, payload, fragment


def dns_hinfo(payload):
    # DNS-over-UDP question type 13; no response labels or attacker identities.
    message = payload[8:]
    if len(message) < 17 or message[2] & 0x80 or int.from_bytes(message[4:6], "big") == 0:
        return False
    index = 12
    while index < len(message):
        size = message[index]
        index += 1
        if size == 0:
            break
        if size & 0xc0 == 0xc0:
            index += 1
            break
        index += size
    return index + 2 <= len(message) and int.from_bytes(message[index:index + 2], "big") == 13


def packet_features(data):
    bins = defaultdict(lambda: np.zeros(len(PACKET_NAMES)))
    sources, targets, ports = defaultdict(set), defaultdict(set), defaultdict(set)
    first = last = None
    total = non_ip = 0
    victim_acks = defaultdict(list)
    for ts, original, packet in pcap_records(data):
        total += 1
        first = ts if first is None else min(first, ts)
        last = ts if last is None else max(last, ts)
        b = int(np.ceil(ts / 60))
        v = bins[b]
        v[0] += 1
        v[1] += original
        parsed = ipv4(packet)
        if parsed is None:
            non_ip += 1
            continue
        protocol, src, dst, sport, dport, payload, fragment = parsed
        sources[b].add(src)
        targets[b].add(dst)
        ports[b].add(dport)
        if protocol == 6 and not fragment and len(payload) >= 14:
            flags = payload[13]
            v[2] += bool(flags & 2)
            v[3] += bool(flags & 16)
            v[4] += bool(flags & 4)
            # Ground truth only: victim identified by independent MIT description.
            if dst == bytes([131, 84, 1, 31]) and flags == 16:
                victim_acks[int(ts)].append((ts, src))
        v[5] += protocol == 17
        v[6] += protocol == 1 and len(payload) > 0 and payload[0] == 8
        v[7] += sport == 53 or dport == 53
        v[8] += protocol == 17 and dport == 53 and dns_hinfo(payload)
        v[9] += dport == 111 or 32768 <= dport <= 34500
        v[10] += dport in [22, 23, 514]
        v[11] += dport in [20, 21]
        v[12] += dport in [6723, 9325, 7983]
    for b, v in bins.items():
        v[13:] = [len(sources[b]), len(targets[b]), len(ports[b])]
    bursts = [{"second": second, "first": min(ts for ts, _ in rows), "packets": len(rows),
               "unique_sources": len(set(src for _, src in rows))}
              for second, rows in sorted(victim_acks.items()) if len(rows) >= 100 and len(set(src for _, src in rows)) >= 100]
    return bins, {"packets": total, "non_ipv4": non_ip, "first": first, "last": last,
                  "victim_ack_flood_bursts": bursts}


def prepare_darpa():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in ["1.0", "2.0.2"]:
        path = ROOT / f"LLS_DDOS_{name}.tar.gz"
        cache = OUT / f"darpa_{name}.npz"
        if cache.exists():
            manifest[name] = json.loads((OUT / f"darpa_{name}_manifest.json").read_text())
            if manifest[name].get("schema_version") == 2:
                continue
        print(f"Reading full captures in {path.name}", flush=True)
        sensor_bins, sensor_details, phase_starts, annotations = {}, {}, defaultdict(list), []
        with tarfile.open(path) as archive:
            for member in archive:
                if not member.isfile():
                    continue
                sensor = "inside" if "tcpdump_inside/" in member.name else "dmz"
                if member.name.endswith(".dump") and "/LLS_DDOS_" in member.name:
                    with archive.extractfile(member) as stream:
                        sensor_bins[sensor], sensor_details[sensor] = packet_features(stream)
                    print(f"Parsed {sensor}: {sensor_details[sensor]['packets']} packets", flush=True)
                elif "mid-level-phase-" in member.name and member.name.endswith(".xml"):
                    with archive.extractfile(member) as stream:
                        content = stream.read().decode("utf-8")
                    root = ET.fromstring(content)
                    phase = int(re.search(r"phase-(\d)", member.name).group(1))
                    # March EST, April EDT; independently checked against capture times.
                    zone = timezone(timedelta(hours=-5 if name == "1.0" else -4))
                    for alert in root.findall(".//Alert"):
                        date, time = alert.findtext("Time/date"), alert.findtext("Time/time")
                        ts = datetime.strptime(date + " " + time, "%m/%d/%Y %H:%M:%S").replace(tzinfo=zone).timestamp()
                        phase_starts[phase].append(ts)
                    annotations.append({"member": member.name, "phase": phase,
                                        "sessions": len(root.findall('.//Alert'))})
        assert set(sensor_bins) == {"inside", "dmz"}
        start = max(d['first'] for d in sensor_details.values())
        end = min(d['last'] for d in sensor_details.values())
        times = np.arange(np.ceil(start / 60) * 60 + 60, np.floor(end / 60) * 60 + 1, 60)
        counts = np.zeros((len(times), len(PACKET_NAMES) * 2))
        for s, sensor in enumerate(["inside", "dmz"]):
            for i, ts in enumerate(times):
                counts[i, s * len(PACKET_NAMES):(s + 1) * len(PACKET_NAMES)] = sensor_bins[sensor].get(int(ts / 60), 0)
        bursts = sensor_details["inside"]["victim_ack_flood_bursts"]
        onset = bursts[0]["first"] if bursts else None
        assert onset is not None and min(phase_starts[5]) <= onset <= end, (name, sensor_details, dict(phase_starts))
        boundaries = [min(phase_starts[p]) for p in [1, 2, 3, 4]] + [onset]
        truth = np.zeros(len(times), dtype=int)
        for p, boundary in enumerate(boundaries, 1):
            truth[times >= boundary] = p
        np.savez_compressed(cache, counts=counts, times=times, truth=truth, onset=onset,
                            names=np.array([s + ":" + f for s in ["inside", "dmz"] for f in PACKET_NAMES]))
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest[name] = {"source": path.name, "sha256": checksum, "schema_version": 2, "sensors": sensor_details,
                          "xml_session_annotations": annotations, "phase_boundaries": boundaries,
                          "phase5_session_start": min(phase_starts[5]), "flood_onset": onset,
                          "phase5_to_flood_seconds": onset - min(phase_starts[5]),
                          "flood_onset_utc": datetime.fromtimestamp(onset, timezone.utc).isoformat(),
                          "clock_bins": len(times), "feature_count": counts.shape[1],
                          "timezone": "EST UTC-5 (March); EDT UTC-4 (April)",
                          "endpoint": "first TCP ACK-only packet in a one-second burst with at least 100 distinct sources and 100 packets to the MIT-documented victim",
                          "endpoint_identity_used_in_features": False}
        (OUT / f"darpa_{name}_manifest.json").write_text(json.dumps(manifest[name], indent=2), encoding="utf-8")
    (OUT / "darpa_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({n: {k:v for k,v in m.items() if k in ['flood_onset_utc','clock_bins','phase5_to_flood_seconds']} for n,m in manifest.items()}), flush=True)


def detector_token(event, sensor):
    if sensor == 2:
        component = event.get("AnalysisComponent", {})
        return "aminer:" + str(component.get("AnalysisComponentType", "unknown")) + ":" + str(component.get("AnalysisComponentIdentifier", "unknown"))
    if sensor == 1:
        return "suricata:" + str(event.get("data", {}).get("alert", {}).get("signature_id", "unknown"))
    rule = event.get("rule", {})
    return "wazuh:" + str(rule.get("id", "unknown"))


def prepare_ait():
    OUT.mkdir(parents=True, exist_ok=True)
    episodes = pilot.load_scenarios()
    with zipfile.ZipFile(pilot.DATA / "ait_ads.zip") as archive:
        for name, ep in episodes.items():
            path = OUT / f"ait_{name}_v2.npz"
            if path.exists():
                print(f"Cached extended AIT {name}", flush=True)
                continue
            bins = defaultdict(Counter)
            seen, token_names = set(), set()
            excluded_training = retained = 0
            for suffix, sensor in [("wazuh", 0), ("aminer", 2)]:
                with archive.open(f"{name}_{suffix}.json") as stream:
                    for line in stream:
                        event = json.loads(line)
                        if sensor == 2 and event.get("AnalysisComponent", {}).get("TrainingMode", False):
                            excluded_training += 1
                            continue
                        record = pilot.parse_record(event, sensor)
                        if record is None or record[0] > ep["onset"] + 1800 or record[3] in seen:
                            continue
                        index = int(np.searchsorted(ep["times"], record[0], side="left"))
                        if index >= len(ep["times"]):
                            continue
                        seen.add(record[3])
                        token = detector_token(event, record[2])
                        token_names.add(token)
                        bins[index][token] += 1
                        retained += 1
            tokens = sorted(token_names)
            mapping = {token:i for i,token in enumerate(tokens)}
            counts = np.zeros((len(ep["times"]), len(tokens)), dtype=np.float32)
            for index, values in bins.items():
                for token, count in values.items():
                    counts[index, mapping[token]] = count
            np.savez_compressed(path, counts=counts, names=np.array(tokens), times=ep["times"],
                                truth=ep["truth"], onset=ep["onset"])
            print(f"Prepared extended AIT {name}: {retained} reports, {len(tokens)} detector tokens; {excluded_training} training-mode records excluded", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["darpa", "ait"])
    args = parser.parse_args()
    {"darpa": prepare_darpa, "ait": prepare_ait}[args.dataset]()

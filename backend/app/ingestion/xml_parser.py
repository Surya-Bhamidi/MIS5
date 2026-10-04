import tarfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class LLDOSXmlParser:
    """
    Parser for DARPA 2000 LLDOS IDMEF XML alert files extracted from tar.gz archives.
    Reused uniformly across LLDOS 1.0 and LLDOS 2.0.2.
    """

    @staticmethod
    def parse_archive(tar_path: Path, max_alerts_per_file: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Reads all 10 Phase 1-5 XML alert files (tcpdump_dmz & tcpdump_inside)
        from a given LLDOS archive and extracts alert records.
        """
        if not tar_path.exists():
            raise FileNotFoundError(f"Dataset archive not found: {tar_path}")

        records: List[Dict[str, Any]] = []

        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                name = member.name
                # Look for tcpdump_dmz/mid-level-phase-X.xml and tcpdump_inside/mid-level-phase-X.xml
                if not name.endswith(".xml") or "mid-level-phase-" not in name:
                    continue

                sensor = "dmz" if "tcpdump_dmz" in name else "inside"
                
                # Extract phase number from filename, e.g. mid-level-phase-3.xml -> 3
                try:
                    phase_str = name.split("mid-level-phase-")[-1].replace(".xml", "")
                    true_phase = int(phase_str)
                except ValueError:
                    logger.warning(f"Could not parse phase number from {name}")
                    continue

                f = tar.extractfile(member)
                if f is None:
                    continue

                content = f.read().decode("utf-8", errors="ignore")
                parsed_alerts = LLDOSXmlParser.parse_xml_content(
                    content,
                    sensor=sensor,
                    true_phase=true_phase,
                    source_file=name,
                    limit=max_alerts_per_file
                )
                records.extend(parsed_alerts)

        return records

    @staticmethod
    def parse_xml_content(
        xml_string: str,
        sensor: str,
        true_phase: int,
        source_file: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse raw XML string containing <IDMEF-Message> and <Alert> nodes.
        Wraps content in a single root if multiple top-level elements exist.
        """
        cleaned = xml_string.strip()
        if not cleaned.startswith("<root>") and not cleaned.startswith("<?xml"):
            cleaned = f"<root>\n{cleaned}\n</root>"
        elif cleaned.startswith("<?xml") and not "<root>" in cleaned:
            # Handle multiple root tags by inserting wrapper after xml declaration
            first_tag_idx = cleaned.find("?>")
            if first_tag_idx != -1:
                cleaned = cleaned[:first_tag_idx+2] + "\n<root>" + cleaned[first_tag_idx+2:] + "</root>"

        alerts: List[Dict[str, Any]] = []

        try:
            root = ET.fromstring(cleaned)
        except ET.ParseError as e:
            # If standard parsing fails due to unclosed tags or entities, parse line by line or recovery
            logger.warning(f"XML parse error on {source_file}: {e}. Retrying with tag chunking.")
            return LLDOSXmlParser._parse_by_chunking(xml_string, sensor, true_phase, source_file, limit)

        alert_nodes = root.findall(".//Alert")
        if limit is not None:
            alert_nodes = alert_nodes[:limit]

        for alert in alert_nodes:
            rec = LLDOSXmlParser._extract_alert_dict(alert, sensor, true_phase, source_file)
            if rec:
                alerts.append(rec)

        return alerts

    @staticmethod
    def _extract_alert_dict(alert_elem: ET.Element, sensor: str, true_phase: int, source_file: str) -> Optional[Dict[str, Any]]:
        """Extracts fields from an <Alert> ElementTree node."""
        alert_id = alert_elem.attrib.get("alertid", "")

        # Time
        time_node = alert_elem.find("Time")
        date_str = time_node.findtext("date") if time_node is not None else ""
        time_str = time_node.findtext("time") if time_node is not None else ""
        duration = time_node.findtext("sessionduration") if time_node is not None else "00:00:00"

        dt_iso = ""
        timestamp_epoch = 0.0
        if date_str and time_str:
            try:
                # Format: MM/DD/YYYY HH:MM:SS
                dt = datetime.strptime(f"{date_str.strip()} {time_str.strip()}", "%m/%d/%Y %H:%M:%S")
                dt_iso = dt.isoformat()
                timestamp_epoch = dt.timestamp()
            except ValueError:
                pass

        # Source
        src_ip = alert_elem.findtext(".//Source/Node/Address/address") or ""
        src_port = (
            alert_elem.findtext(".//Source/Service/port") or
            alert_elem.findtext(".//Source/Service/sport") or
            alert_elem.findtext(".//Target/Service/sport") or ""
        )

        # Target
        dst_ip = alert_elem.findtext(".//Target/Node/Address/address") or ""
        dst_port = (
            alert_elem.findtext(".//Target/Service/dport") or
            alert_elem.findtext(".//Target/Service/port") or ""
        )
        service_name = alert_elem.findtext(".//Target/Service/name") or ""

        # Analyzer
        analyzer_name = alert_elem.findtext(".//Analyzer/name") or sensor

        return {
            "alert_id": alert_id,
            "date": date_str,
            "time": time_str,
            "timestamp_iso": dt_iso,
            "timestamp": timestamp_epoch,
            "session_duration": duration,
            "sensor_source": sensor,
            "analyzer": analyzer_name,
            "src_ip": src_ip.strip(),
            "src_port": src_port.strip(),
            "dst_ip": dst_ip.strip(),
            "dst_port": dst_port.strip(),
            "service_name": service_name.strip(),
            "true_phase_label": true_phase,
            "source_file": source_file,
        }

    @staticmethod
    def _parse_by_chunking(
        content: str,
        sensor: str,
        true_phase: int,
        source_file: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fallback chunker for malformed IDMEF blocks."""
        alerts: List[Dict[str, Any]] = []
        chunks = content.split("<Alert ")
        for chunk in chunks[1:]:
            if limit is not None and len(alerts) >= limit:
                break
            full_chunk = "<Alert " + chunk
            end_idx = full_chunk.find("</Alert>")
            if end_idx == -1:
                continue
            alert_xml = full_chunk[:end_idx + 8]
            try:
                alert_elem = ET.fromstring(alert_xml)
                rec = LLDOSXmlParser._extract_alert_dict(alert_elem, sensor, true_phase, source_file)
                if rec:
                    alerts.append(rec)
            except Exception:
                continue
        return alerts

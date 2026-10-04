import sys
import time
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.config import LLDOS_1_TAR, LLDOS_2_TAR, DB_PATH
from app.ingestion.xml_parser import LLDOSXmlParser
from app.ingestion.normalizer import EventNormalizer
from app.ingestion.synthetic_generator import SyntheticEventGenerator
from app.ingestion.database import Database

def run_full_ingestion():
    print("=" * 60)
    print("Starting LLDOS Cyber Threat Ingestion Pipeline...")
    print("=" * 60)
    
    db = Database(DB_PATH)
    t0 = time.time()

    # 1. Ingest LLDOS 1.0 (Inside + DMZ, Phase 1-5)
    print(f"\n[1/3] Parsing LLDOS 1.0 from: {LLDOS_1_TAR}...")
    t_parse = time.time()
    # For Phase 5 DDoS, capping at 3,000 alerts per file keeps the dataset rich and representative
    # while guaranteeing sub-second response times for real-time web playback and cross-validation
    raw_lldos1 = LLDOSXmlParser.parse_archive(LLDOS_1_TAR, max_alerts_per_file=3000)
    print(f"  Parsed {len(raw_lldos1)} alerts from XML files in {time.time() - t_parse:.2f}s")
    
    print("  Normalizing and merging Inside + DMZ with sensor co-occurrence tagging...")
    norm_lldos1 = EventNormalizer.normalize_and_merge(raw_lldos1, cooccur_window_sec=3.0)
    db.insert_events("events_lldos1", norm_lldos1)
    cooccur_count1 = sum(1 for e in norm_lldos1 if e["session_cooccurred"])
    print(f"  Persisted {len(norm_lldos1)} events to 'events_lldos1' ({cooccur_count1} dual-sensor co-occurred).")

    # 2. Ingest LLDOS 2.0.2 (Held-out Evaluation Dataset)
    print(f"\n[2/3] Parsing LLDOS 2.0.2 (Evaluation Set) from: {LLDOS_2_TAR}...")
    t_parse = time.time()
    raw_lldos2 = LLDOSXmlParser.parse_archive(LLDOS_2_TAR)
    print(f"  Parsed {len(raw_lldos2)} alerts from XML files in {time.time() - t_parse:.2f}s")
    
    print("  Normalizing and merging Inside + DMZ...")
    norm_lldos2 = EventNormalizer.normalize_and_merge(raw_lldos2, cooccur_window_sec=3.0)
    db.insert_events("events_lldos2", norm_lldos2)
    cooccur_count2 = sum(1 for e in norm_lldos2 if e["session_cooccurred"])
    print(f"  Persisted {len(norm_lldos2)} events to 'events_lldos2' ({cooccur_count2} dual-sensor co-occurred).")

    # 3. Generate initial Synthetic Stream
    print("\n[3/3] Generating Synthetic Markov Chain Event Sequence...")
    syn_gen = SyntheticEventGenerator(noise_rate=0.08, missing_alert_rate=0.05, seed=42)
    syn_events = syn_gen.generate_sequence(n_steps=150)
    db.insert_events("events_synthetic", syn_events, run_id="default_run")
    print(f"  Generated and persisted {len(syn_events)} synthetic events to 'events_synthetic'.")

    # Summary verification
    print("\n" + "=" * 60)
    print("Ingestion Pipeline Completed Successfully!")
    print(f"Total time elapsed: {time.time() - t0:.2f}s")
    print(f"Database location: {DB_PATH}")
    print(f"  - events_lldos1 count: {db.get_event_count('events_lldos1')}")
    print(f"  - events_lldos2 count: {db.get_event_count('events_lldos2')}")
    print(f"  - events_synthetic count: {db.get_event_count('events_synthetic', run_id='default_run')}")
    print("=" * 60)

if __name__ == "__main__":
    run_full_ingestion()

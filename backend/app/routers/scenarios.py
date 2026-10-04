from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.config import DB_PATH, THREAT_STATES, PHASE_LABELS
from app.ingestion.database import Database
from app.ingestion.synthetic_generator import SyntheticEventGenerator

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])
db = Database(DB_PATH)

class SyntheticGenRequest(BaseModel):
    noise_rate: float = 0.08
    missing_alert_rate: float = 0.05
    n_steps: int = 120
    run_id: str = "custom_run"

@router.get("")
def list_scenarios():
    """Lists available scenarios with alert counts and phase breakdowns."""
    scenarios = [
        {
            "id": "events_lldos1",
            "name": "LLDOS 1.0 (Train / Calibration)",
            "type": "real",
            "description": "Novice attacker executing 5-phase kill chain: IPsweep -> Sadmind Ping -> Sadmind Breakin -> Trojan Mstream Install -> DDoS Launch.",
            "total_alerts": db.get_event_count("events_lldos1"),
            "role": "training_dev",
            "held_out": False,
        },
        {
            "id": "events_lldos2",
            "name": "LLDOS 2.0.2 (Held-Out Test)",
            "type": "real",
            "description": "Stealthier attacker with condensed footprint: DNS queries -> Sadmind exploit -> FTP staging -> SSH launch -> Mail receipt. Used strictly for evaluation (RQ4).",
            "total_alerts": db.get_event_count("events_lldos2"),
            "role": "held_out_test",
            "held_out": True,
        },
        {
            "id": "events_synthetic",
            "name": "Synthetic Markov Chain Stream",
            "type": "synthetic",
            "description": "Configurable stochastic sequence generator over 6 states with injected background noise and packet evasion.",
            "total_alerts": db.get_event_count("events_synthetic", run_id="default_run"),
            "role": "sensitivity_ablation",
            "held_out": False,
        }
    ]
    return {"scenarios": scenarios, "states": THREAT_STATES, "phase_labels": PHASE_LABELS}

@router.get("/{scenario_id}/alerts")
def get_scenario_alerts(
    scenario_id: str,
    limit: Optional[int] = Query(default=100, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    phase: Optional[int] = Query(default=None),
    run_id: Optional[str] = Query(default=None)
):
    """Retrieves normalized alerts for the specified scenario with pagination."""
    valid_tables = ["events_lldos1", "events_lldos2", "events_synthetic"]
    if scenario_id not in valid_tables:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    r_id = run_id if scenario_id == "events_synthetic" else None
    if scenario_id == "events_synthetic" and not r_id:
        r_id = "default_run"

    events = db.get_events(scenario_id, limit=limit, offset=offset, run_id=r_id, phase=phase)
    total = db.get_event_count(scenario_id, run_id=r_id)

    return {
        "scenario_id": scenario_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": events,
    }

@router.post("/synthetic/generate")
def generate_synthetic_scenario(req: SyntheticGenRequest):
    """Generates a new synthetic scenario run and stores it in SQLite."""
    gen = SyntheticEventGenerator(
        noise_rate=req.noise_rate,
        missing_alert_rate=req.missing_alert_rate,
        seed=int(req.noise_rate * 1000) + int(req.missing_alert_rate * 1000) + 42
    )
    events = gen.generate_sequence(n_steps=req.n_steps)
    db.insert_events("events_synthetic", events, run_id=req.run_id)

    return {
        "status": "success",
        "run_id": req.run_id,
        "generated_count": len(events),
        "noise_rate": req.noise_rate,
        "missing_alert_rate": req.missing_alert_rate,
    }

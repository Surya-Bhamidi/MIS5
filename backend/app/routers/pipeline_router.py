from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.config import DB_PATH
from app.ingestion.database import Database
from app.models.pipeline import CyberPipeline

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])

db = Database(DB_PATH)
# Global singleton pipeline instance initialized with training data
pipeline = CyberPipeline()
train_events = db.get_events("events_lldos1", limit=1200)
pipeline.fit_from_training_events(train_events)

class AlertInferRequest(BaseModel):
    alert: Dict[str, Any]
    ablation_mode: str = "B3"

class BatchInferRequest(BaseModel):
    scenario_id: str
    limit: int = 150
    ablation_mode: str = "B3"
    run_id: Optional[str] = None

@router.post("/infer")
def infer_step(req: AlertInferRequest):
    """Processes a single alert through the 4-stage pipeline."""
    if req.ablation_mode not in ["B0", "B1", "B2", "B3"]:
        raise HTTPException(status_code=400, detail="Ablation mode must be one of ['B0', 'B1', 'B2', 'B3']")

    out = pipeline.process_event(req.alert, ablation_mode=req.ablation_mode)
    return out

@router.post("/batch")
def infer_batch(req: BatchInferRequest):
    """Processes an entire alert sequence for a given scenario."""
    r_id = req.run_id if req.scenario_id == "events_synthetic" else None
    if req.scenario_id == "events_synthetic" and not r_id:
        r_id = "default_run"

    events = db.get_events(req.scenario_id, limit=req.limit, run_id=r_id)
    if not events:
        raise HTTPException(status_code=404, detail="No events found for scenario")

    pipeline.reset_stream_state()
    steps = []
    for e in events:
        step_res = pipeline.process_event(e, ablation_mode=req.ablation_mode)
        steps.append(step_res)

    return {
        "scenario_id": req.scenario_id,
        "ablation_mode": req.ablation_mode,
        "total_processed": len(steps),
        "steps": steps,
    }

@router.post("/reset")
def reset_pipeline():
    """Resets temporal filtering state."""
    pipeline.reset_stream_state()
    return {"status": "pipeline_reset_complete"}

@router.get("/matrices")
def get_model_matrices():
    """Returns HMM transition and emission matrices for visual inspection."""
    return {
        "hmm_matrices": pipeline.hmm.get_matrices_dict(),
        "utility_matrix": pipeline.dn.utilities,
    }

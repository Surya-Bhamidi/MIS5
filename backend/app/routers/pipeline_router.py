from fastapi import APIRouter, HTTPException,Request,Response
from pydantic import BaseModel,Field,ConfigDict
from threading import RLock
import time
import uuid
from typing import Dict, Any, List, Optional

from app.config import DB_PATH
from app.ingestion.database import Database
from app.models.pipeline import CyberPipeline
from app.routers.legacy_schemas import LegacyAlert,Ablation,Scenario

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])
pipeline_lock=RLock()
contexts={}
COOKIE='mis5_demo_session'

db = Database(DB_PATH)
# Global singleton pipeline instance initialized with training data
pipeline = CyberPipeline()
train_events = db.get_events("events_lldos1", limit=1200)
pipeline.fit_from_training_events(train_events)


def own_pipeline(request,response):
    now=time.time()
    for identifier in list(contexts):
        if now-contexts[identifier]['touched']>3600:del contexts[identifier]
    identifier=request.cookies.get(COOKIE)
    if identifier not in contexts:
        if len(contexts)>=32:raise HTTPException(429,'Legacy session limit reached')
        identifier=uuid.uuid4().hex
        contexts[identifier]=dict(pipeline=CyberPipeline(bn=pipeline.bn,hmm=pipeline.hmm,dn=pipeline.dn),touched=now)
    contexts[identifier]['touched']=now
    response.set_cookie(COOKIE,identifier,max_age=3600,httponly=True,samesite='strict',path='/api/pipeline')
    return contexts[identifier]['pipeline']

class AlertInferRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    alert: LegacyAlert
    ablation_mode: Ablation = 'B3'

class BatchInferRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scenario_id: Scenario
    limit: int = Field(150,ge=1,le=500,strict=True)
    ablation_mode: Ablation = 'B3'
    run_id: Optional[str] = Field(None,min_length=1,max_length=128)

@router.post("/infer")
def infer_step(req: AlertInferRequest,request:Request,response:Response):
    """Processes a single alert through the 4-stage pipeline."""
    if req.ablation_mode not in ["B0", "B1", "B2", "B3"]:
        raise HTTPException(status_code=400, detail="Ablation mode must be one of ['B0', 'B1', 'B2', 'B3']")

    with pipeline_lock:
        local=own_pipeline(request,response)
        if local.history_events and req.alert.timestamp<local.history_events[-1]['timestamp']:
            raise HTTPException(409,'Reset the legacy stream before sending an earlier timestamp')
        out = local.process_event(req.alert.model_dump(exclude_none=True), ablation_mode=req.ablation_mode)
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

    try:
        events=[LegacyAlert.model_validate(e).model_dump(exclude_none=True) for e in events]
    except ValueError as error:
        raise HTTPException(503,'Stored scenario contains invalid normalized alerts') from error
    # Each batch owns its temporal state. Replaying a past row or another mode
    # cannot reuse a future belief or reset an unrelated caller's stream.
    local=CyberPipeline(bn=pipeline.bn,hmm=pipeline.hmm,dn=pipeline.dn)
    steps=[local.process_event(e,ablation_mode=req.ablation_mode) for e in events]

    return {
        "scenario_id": req.scenario_id,
        "ablation_mode": req.ablation_mode,
        "total_processed": len(steps),
        "steps": steps,
    }

@router.post("/reset")
def reset_pipeline(request:Request,response:Response):
    """Resets temporal filtering state."""
    with pipeline_lock: own_pipeline(request,response).reset_stream_state()
    return {"status": "pipeline_reset_complete"}

@router.get("/matrices")
def get_model_matrices():
    """Returns HMM transition and emission matrices for visual inspection."""
    return {
        "hmm_matrices": pipeline.hmm.get_matrices_dict(),
        "utility_matrix": pipeline.dn.utilities,
    }

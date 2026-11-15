from fastapi import APIRouter, HTTPException
from pydantic import BaseModel,ConfigDict,field_validator
from typing import Dict, Any, Optional,Literal

from app.config import DEFENSIVE_ACTIONS
from app.models.decision_network import ResponseDecisionNetwork

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])
dn = ResponseDecisionNetwork()

class WhatIfRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    current_belief: Dict[str, float]
    hypothetical_action: Literal['Monitor','Restrict','Block','Isolate']
    baseline_action: Literal['Monitor','Restrict','Block','Isolate'] = 'Monitor'

    @field_validator('current_belief')
    @classmethod
    def valid_distribution(cls,value):return ResponseDecisionNetwork.validate_belief(value)

@router.post("/what-if")
def simulate_counterfactual(req: WhatIfRequest):
    """
    Simulates hypothetical defensive intervention against internal threat model
    and projects 5-step risk/loss trajectory compared to passive monitoring baseline.
    """
    if req.hypothetical_action not in DEFENSIVE_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid hypothetical action '{req.hypothetical_action}'. Must be one of {DEFENSIVE_ACTIONS}."
        )

    sim_res = dn.simulate_what_if(
        current_belief=req.current_belief,
        hypothetical_action=req.hypothetical_action,
        baseline_action=req.baseline_action or "Monitor"
    )
    return sim_res

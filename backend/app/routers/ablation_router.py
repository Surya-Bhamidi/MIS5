from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional

from app.config import DB_PATH
from app.ingestion.database import Database
from app.evaluation.experiment_runner import ExperimentRunner

router = APIRouter(prefix="/api/ablation", tags=["Ablation"])
db = Database(DB_PATH)
runner = ExperimentRunner(db)

@router.get("/{scenario_id}")
def get_ablation_results(scenario_id: str):
    """
    Returns comparative performance metrics across B0, B1, B2, and B3
    for the specified scenario.
    """
    valid_tables = ["events_lldos1", "events_lldos2", "events_synthetic"]
    if scenario_id not in valid_tables:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    saved = db.get_experiment_result(f"ablation_{scenario_id}")
    if saved:
        return saved

    # Compute on-demand if not cached
    res = runner.run_ablation_study(scenario_id)
    return res

@router.post("/run-all")
def run_all_ablations():
    """Runs ablation comparison across all three data sources."""
    res_1 = runner.run_ablation_study("events_lldos1")
    res_2 = runner.run_ablation_study("events_lldos2")
    res_syn = runner.run_ablation_study("events_synthetic")

    return {
        "LLDOS_1.0": res_1,
        "LLDOS_2.0.2": res_2,
        "Synthetic": res_syn,
    }

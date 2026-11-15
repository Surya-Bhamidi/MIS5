from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.config import DB_PATH
from app.ingestion.database import Database
from app.evaluation.experiment_runner import ExperimentRunner
from app.evaluation.serialization import serialized
from threading import RLock

router = APIRouter(prefix="/api/experiments", tags=["Experiments"])
db = Database(DB_PATH)
runner = ExperimentRunner(db)
runner_lock=RLock()

@router.get("")
@serialized(runner_lock)
def get_all_experiments():
    """Returns saved results for all research questions (RQ1 through RQ5)."""
    results = db.get_all_experiment_results()
    # Check if results are empty, compute on-demand if so
    if not results or "RQ1" not in results:
        runner.run_rq1_bn_inference()
        runner.run_rq2_hmm_prediction()
        runner.run_rq3_decision_utility()
        runner.run_rq4_generalization_and_robustness()
        runner.run_rq5_provenance_audit()
        results = db.get_all_experiment_results()

    return results

@router.get("/{rq_id}")
@serialized(runner_lock)
def get_experiment_detail(rq_id: str):
    """Returns detailed metrics and charts for a specific RQ."""
    key = rq_id.upper()
    res = db.get_experiment_result(key)
    if not res:
        if key == "RQ1": res = runner.run_rq1_bn_inference()
        elif key == "RQ2": res = runner.run_rq2_hmm_prediction()
        elif key == "RQ3": res = runner.run_rq3_decision_utility()
        elif key == "RQ4": res = runner.run_rq4_generalization_and_robustness()
        elif key == "RQ5": res = runner.run_rq5_provenance_audit()
        else:
            raise HTTPException(status_code=404, detail=f"Experiment '{rq_id}' not found")

    return res

@router.post("/rerun")
@serialized(runner_lock)
def rerun_experiments():
    """Forces re-execution of all research questions."""
    rq1 = runner.run_rq1_bn_inference()
    rq2 = runner.run_rq2_hmm_prediction()
    rq3 = runner.run_rq3_decision_utility()
    rq4 = runner.run_rq4_generalization_and_robustness()
    rq5 = runner.run_rq5_provenance_audit()

    return {
        "status": "success",
        "message": "All experiments re-evaluated successfully",
        "results": {
            "RQ1": rq1,
            "RQ2": rq2,
            "RQ3": rq3,
            "RQ4": rq4,
            "RQ5": rq5,
        }
    }

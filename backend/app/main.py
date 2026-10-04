from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import (
    scenarios,
    pipeline_router,
    simulation_router,
    ablation_router,
    experiments_router,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Probabilistic Cyber Threat Progression & Response API",
    description="Transparent, modular decision-support system integrating Bayesian Network, Hidden Markov Model, and Decision Network.",
    version="1.0.0"
)

# Enable CORS for frontend Vite client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios.router)
app.include_router(pipeline_router.router)
app.include_router(simulation_router.router)
app.include_router(ablation_router.router)
app.include_router(experiments_router.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Probabilistic Cyber Threat Progression & Response",
        "version": "1.0.0"
    }

@app.get("/api")
def root_info():
    return {
        "name": "Probabilistic Cyber Threat Progression & Response API",
        "endpoints": [
            "/api/health",
            "/api/scenarios",
            "/api/pipeline/infer",
            "/api/pipeline/batch",
            "/api/pipeline/matrices",
            "/api/simulation/what-if",
            "/api/ablation/{scenario_id}",
            "/api/experiments",
        ]
    }

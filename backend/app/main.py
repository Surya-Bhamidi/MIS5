from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.request_safety import LocalRequestGuard,LOCAL_ORIGINS,validation_response
import logging

from app.routers import (
    scenarios,
    pipeline_router,
    simulation_router,
    ablation_router,
    experiments_router,
    research_router,
    live_router,
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
    allow_origins=list(LOCAL_ORIGINS),
    allow_credentials=False,
    allow_methods=['GET','POST','DELETE'],
    allow_headers=['Content-Type'],
)
app.add_middleware(LocalRequestGuard)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]'])
app.add_exception_handler(RequestValidationError,validation_response)

app.include_router(scenarios.router)
app.include_router(pipeline_router.router)
app.include_router(simulation_router.router)
app.include_router(ablation_router.router)
app.include_router(experiments_router.router)
app.include_router(research_router.router)
app.include_router(live_router.router)

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
            "/api/research/overview",
            "/api/research/replay/{campaign}",
            "/api/live/status",
            "/api/live/report",
            "/api/live/streams",
            "/api/scenarios",
            "/api/pipeline/infer",
            "/api/pipeline/batch",
            "/api/pipeline/matrices",
            "/api/simulation/what-if",
            "/api/ablation/{scenario_id}",
            "/api/experiments",
        ]
    }

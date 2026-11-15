"""Read-only dashboard for frozen AIT forecasts; never trains or executes defenses."""
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.artifact_store import verified_json, verified_bytes, decoded_archive

ROOT = Path(__file__).resolve().parents[3]
CURRENT = ROOT / "experiments/current_version"
FULL = "aminer+suricata+wazuh"
CAMPAIGNS = ("fox", "harrison", "russellmitchell", "santos", "shaw", "wardbeck", "wheeler", "wilson")
MODES = ("temporal_boosting", "conditional_fusion", "pooled_counts", "pooled_fixed_blend")
LABELS = ("Original counts", "Earlier hybrid", "Matched counts", "Current hybrid")
COLORS = ("#60a5fa", "#a78bfa", "#94a3b8", "#2dd4bf")
SENSORS = (FULL, "aminer+suricata", "aminer+wazuh", "suricata+wazuh", "aminer", "suricata", "wazuh", "none")
ACTIONS = (("Monitor", 0, 0., 0.), ("Restrict", 2, .45, .1), ("Block", 5, .8, .5), ("Isolate", 1, .95, 2.))
router = APIRouter(prefix="/api/research", tags=["Current research dashboard"])


def read(relative):
    return verified_json(relative)


def selected(rows, mode, horizon, available=FULL):
    return [r for r in rows if r["mode"] == mode and r["horizon"] == horizon
            and r["endpoint"] == "successful_root" and r["budget"] == 1
            and r.get("available", FULL) == available and r.get("delay_minutes", 0) == 0]


@router.get("/overview")
def overview(horizon: int = Query(30, ge=15, le=30), available: str = FULL):
    if horizon not in (15, 30) or available not in SENSORS:
        raise HTTPException(422, "Choose horizon 15 or 30 and a declared sensor configuration")
    config = read("experiments/current_version/config.json")
    verification = read("experiments/current_version/verification.json")
    if available == "none":
        return {"status": "insufficient_sensors", "config": config, "models": [], "campaigns": [], "sensors": SENSORS}
    models = []
    for mode, label, color in zip(MODES, LABELS, COLORS):
        if mode in MODES[:2] and available != FULL:
            continue
        path = ("experiments/published_comparison/budget_summary.json" if mode in MODES[:2]
                else "experiments/current_version/summary.json" if mode == MODES[-1]
                else "experiments/selective_fusion/summary.json")
        result = selected(read(path), mode, horizon, available)
        if len(result) != 1:
            raise HTTPException(503, "Requested research comparison is incomplete")
        models.append({**result[0], "label": label, "color": color})
    scored = read("experiments/selective_fusion/scored.json")
    cases = []
    for name in CAMPAIGNS:
        pair = {}
        for mode in MODES[2:]:
            found = [r for r in selected(scored, mode, horizon, available) if r["scenario"] == name]
            if len(found) != 1:
                raise HTTPException(503, "Requested campaign comparison is incomplete")
            pair[mode] = found[0]
        cases.append({"name": name, "hybrid": pair[MODES[-1]], "counts": pair[MODES[2]]})
    return {"status": "ok", "config": config, "verified": verification["passed"],
            "regression_tests": verification["regression_tests"], "horizon": horizon, "available": available,
            "models": models, "campaigns": cases, "sensors": SENSORS,
            "scope": "Frozen exploratory forecasts; preset selected after reviewing these eight campaigns"}


def modeled_losses(risk, horizons):
    """Same delay/effect formula and default assumptions as extended_study.decision_costs."""
    chance = risk[:, horizons.index(30)]
    result = []
    for _, delay, effect, disruption in ACTIONS:
        late = risk[:, horizons.index(delay)] if delay else np.zeros(len(risk))
        result.append(disruption + 20 * (chance - min(1, effect * .8) * np.maximum(0, chance - late)))
    return np.stack(result, axis=1)


def archive(name, available):
    path = CURRENT / "predictions" / f"ait_{name}_{available}_pooled_fixed_blend.npz"
    return decoded_archive(verified_bytes(path.relative_to(ROOT).as_posix()))


@router.get("/replay/{campaign}")
def replay(campaign: str, available: str = FULL, horizon: int = 30,
           window_minutes: int = Query(180, ge=30, le=1440)):
    if campaign not in CAMPAIGNS or available not in SENSORS or horizon not in (15, 30):
        raise HTTPException(422, "Unknown campaign, sensor configuration or horizon")
    if available == "none":
        return {"status": "insufficient_sensors", "points": [], "recommended_action": None}
    data = archive(campaign, available)
    evidence = next(r for r in read("experiments/publication_validation/endpoint_evidence.json") if r["scenario"] == campaign)
    endpoint = evidence["successful_root"]
    horizons = data["horizons"].tolist()
    scores = selected(read("experiments/selective_fusion/scored.json"), MODES[-1], horizon, available)
    score = next(r for r in scores if r["scenario"] == campaign)
    threshold = score["threshold"]
    offsets = (data["times"] - endpoint) / 60
    mask = (offsets >= -window_minutes) & (offsets < 0)
    indices = np.flatnonzero(mask)
    risk = data["risk"][mask]
    losses = modeled_losses(risk, horizons)
    alarms = data["risk"][:, horizons.index(horizon)] >= threshold
    # Determine episode starts using the complete archive, before slicing the visible window.
    starts = alarms & ~np.r_[False, alarms[:-1]]
    points = [{"timestamp": float(data["times"][i]), "minutes_before": float(-offsets[i]),
               "risk": risk[j].tolist(), "warning": bool(alarms[i]), "episode_start": bool(starts[i]),
               "recommended_action": ACTIONS[int(losses[j].argmin())][0], "modeled_losses": losses[j].tolist()}
              for j, i in enumerate(indices)]
    return {"status": "ok", "campaign": campaign, "available": available, "horizon": horizon,
            "horizons": horizons, "threshold": threshold, "endpoint": endpoint,
            "score": score, "points": points, "actions": [a[0] for a in ACTIONS],
            "response_assumptions": {"damage": 20, "effect_scale": .8, "disruption_scale": 1},
            "scope": "Archived pre-outcome replay; endpoint shown for retrospective evaluation only"}


ASSETS = {f"{stem}.{ext}": ROOT / "Plots/Results/mids" / f"{stem}.{ext}"
          for stem in ("01_timely_warning_coverage", "02_probability_error", "03_alarm_tradeoff")
          for ext in ("png", "pdf")}
ASSETS["metrics.csv"] = ROOT / "Plots/Results/mids/all_metrics_15_30_minutes.csv"


@router.get("/assets/{name}")
def asset(name: str):
    path = ASSETS.get(name)
    if path is None or not path.is_file():
        raise HTTPException(404, "Research asset unavailable")
    content = verified_bytes(path.relative_to(ROOT).as_posix())
    media = {'.csv': 'text/csv', '.pdf': 'application/pdf', '.png': 'image/png'}[path.suffix]
    return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="{path.name}"'})

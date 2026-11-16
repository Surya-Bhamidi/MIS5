"""Export checksum-checked dashboard evidence for a frontend-only presentation.

Run from the repository root: python backend/research/export_showcase.py
No fitting, tuning, or synthetic forecasts are performed.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.routers.research_router import CAMPAIGNS, SENSORS, ASSETS, overview, replay
from app.artifact_store import verified_bytes

OUTPUT = ROOT / "frontend/public/demo"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def main():
    manifest = {"description": "Saved research evidence; source checksums verified during export.",
                "preset": "pooled_fixed_blend", "files": {}}
    for horizon in (15, 30):
        for available in SENSORS:
            write_json(OUTPUT / f"overview-{horizon}-{available}.json", overview(horizon, available))
            if available == "none":
                continue
            for campaign in CAMPAIGNS:
                write_json(OUTPUT / f"replay-{campaign}-{horizon}-{available}.json",
                           replay(campaign, available, horizon, window_minutes=180))
    for name, source in ASSETS.items():
        destination = OUTPUT / "plots" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(verified_bytes(source.relative_to(ROOT).as_posix()))
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest["files"][path.relative_to(OUTPUT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(OUTPUT / "manifest.json", manifest)
    print(f"Exported {len(manifest['files'])} verified evidence files to {OUTPUT}")


if __name__ == "__main__":
    main()

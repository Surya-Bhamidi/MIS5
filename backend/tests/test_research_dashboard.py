"""Check dashboard views against original frozen evidence, not copied UI constants."""
from pathlib import Path
import sys
import unittest

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.routers import research_router as research


class TestResearchDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(research.router)
        cls.client = TestClient(app)

    def test_aggregate_views_match_campaign_scores_for_every_sensor_setting(self):
        for horizon in (15, 30):
            for available in research.SENSORS[:-1]:
                response = self.client.get("/api/research/overview", params={"horizon": horizon, "available": available})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                for mode, key in (("pooled_counts", "counts"), ("pooled_fixed_blend", "hybrid")):
                    model = next(m for m in data["models"] if m["mode"] == mode)
                    scores = [c[key] for c in data["campaigns"]]
                    self.assertEqual(model["strict_warned"], sum(c["strict_warning_recall"] for c in scores))
                    self.assertEqual(model["false_episodes"], sum(c["false_warning_episodes"] for c in scores))
                    self.assertAlmostEqual(model["mean_brier"], np.mean([c["brier"] for c in scores]), places=12)
                    self.assertAlmostEqual(model["mean_ap"], np.mean([c["average_precision"] for c in scores]), places=12)

    def test_replay_has_exact_frozen_probabilities_and_verified_endpoint(self):
        for campaign in research.CAMPAIGNS:
            data = self.client.get(f"/api/research/replay/{campaign}").json()
            archive = research.archive(campaign, research.FULL)
            indices = np.flatnonzero((archive["times"] >= data["endpoint"] - 180*60) & (archive["times"] < data["endpoint"]))
            np.testing.assert_array_equal([p["risk"] for p in data["points"]], archive["risk"][indices])
            self.assertTrue(all(p["timestamp"] < data["endpoint"] for p in data["points"]))
            hi = data["horizons"].index(30)
            alarms = archive["risk"][:, hi] >= data["threshold"]
            starts = alarms & ~np.r_[False, alarms[:-1]]
            self.assertEqual([p["episode_start"] for p in data["points"]], starts[indices].tolist())
            timely = [p for p in data["points"] if p["episode_start"] and p["minutes_before"] <= 30]
            self.assertEqual(bool(timely), bool(data["score"]["strict_warning_recall"]))

    def test_response_costs_match_research_decision_network_formula(self):
        sys.path.insert(0, str(ROOT / "backend/research"))
        import extended_study
        data = self.client.get("/api/research/replay/fox").json()
        risk = np.array([p["risk"] for p in data["points"]])
        expected = extended_study.decision_costs(risk, True, 20, .8, 1)
        np.testing.assert_allclose([p["modeled_losses"] for p in data["points"]], expected, rtol=0, atol=1e-12)
        self.assertEqual([p["recommended_action"] for p in data["points"]], [extended_study.ACTIONS[i][0] for i in expected.argmin(axis=1)])

    def test_no_sensors_abstains_in_both_views(self):
        for path in ("overview", "replay/fox"):
            data = self.client.get(f"/api/research/{path}?available=none").json()
            self.assertEqual(data["status"], "insufficient_sensors")
            self.assertFalse(data.get("models") or data.get("points"))

    def test_invalid_filters_and_paths_cannot_open_files(self):
        for path in ("overview?horizon=20", "overview?available=unknown", "replay/unknown", "replay/fox?available=unknown"):
            self.assertEqual(self.client.get(f"/api/research/{path}").status_code, 422)
        self.assertEqual(self.client.get("/api/research/assets/config.json").status_code, 404)

    def test_download_returns_exact_existing_file(self):
        response = self.client.get("/api/research/assets/metrics.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, research.ASSETS["metrics.csv"].read_bytes())


if __name__ == "__main__":
    unittest.main()

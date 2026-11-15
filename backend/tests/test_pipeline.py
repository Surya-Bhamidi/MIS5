import unittest
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DB_PATH
from app.ingestion.database import Database
from app.models.bayesian_network import ThreatStateBayesianNetwork
from app.models.hmm_model import CyberAttackHMM
from app.models.decision_network import ResponseDecisionNetwork
from app.models.pipeline import CyberPipeline

class TestPipelineComponents(unittest.TestCase):
    def setUp(self):
        self.pipeline.reset_stream_state()

    @classmethod
    def setUpClass(cls):
        cls.db = Database(DB_PATH)
        cls.train_events = cls.db.get_events("events_lldos1", limit=400)
        cls.pipeline = CyberPipeline()
        cls.pipeline.fit_from_training_events(cls.train_events)

    def test_bayesian_network_inference(self):
        evidence = {
            "signature_category": "ICMP_SWEEP",
            "target_diversity": "MULTI_HOST",
            "port_class": "STANDARD",
            "sensor_corroboration": "DUAL_SENSOR",
            "alert_rate": "MEDIUM"
        }
        res = self.pipeline.bn.infer_threat_state(evidence)
        dist = res["posterior_distribution"]
        self.assertAlmostEqual(sum(dist.values()), 1.0, places=3)
        self.assertIn("top_state", res)
        self.assertIn("feature_attributions", res)

    def test_hmm_forward_and_projection(self):
        hmm = self.pipeline.hmm
        self.assertTrue(hmm.fitted)
        self.assertEqual(hmm.A.shape, (6, 6))
        self.assertEqual(hmm.B.shape, (6, 6))

        # Check row stochastic
        for row in hmm.A:
            self.assertAlmostEqual(float(row.sum()), 1.0, places=4)

        projections = hmm.project_progression(hmm.pi, horizon=2)
        self.assertEqual(len(projections), 2)
        for proj in projections:
            self.assertAlmostEqual(sum(proj.values()), 1.0, places=3)

    def test_decision_network_evaluation(self):
        dn = self.pipeline.dn
        # Test extreme ActiveAttack belief
        critical_belief = {
            "Benign": 0.01,
            "Recon": 0.01,
            "Discovery": 0.01,
            "Compromise": 0.02,
            "PrivEsc": 0.05,
            "ActiveAttack": 0.90
        }
        rec = dn.evaluate_actions(critical_belief)
        self.assertEqual(rec["recommended_action"], "Isolate")
        self.assertIn("ranked_actions", rec)

        # Test benign belief
        benign_belief = {
            "Benign": 0.95,
            "Recon": 0.02,
            "Discovery": 0.01,
            "Compromise": 0.01,
            "PrivEsc": 0.005,
            "ActiveAttack": 0.005
        }
        rec_benign = dn.evaluate_actions(benign_belief)
        self.assertEqual(rec_benign["recommended_action"], "Monitor")

    def test_what_if_simulation(self):
        dn = self.pipeline.dn
        belief = {"Compromise": 0.80, "Benign": 0.05, "Recon": 0.05, "Discovery": 0.05, "PrivEsc": 0.03, "ActiveAttack": 0.02}
        whatif = dn.simulate_what_if(belief, hypothetical_action="Block", baseline_action="Monitor")
        self.assertIn("utility_delta", whatif)
        self.assertIn("loss_trajectories", whatif)
        self.assertGreater(whatif["utility_delta"], 0)

    def test_pipeline_step_processing(self):
        sample_event = self.train_events[0]
        step_res = self.pipeline.process_event(sample_event, ablation_mode="B3")
        self.assertIn("bn_belief", step_res)
        self.assertIn("hmm_belief", step_res)
        self.assertIn("combined_belief", step_res)
        self.assertIn("recommendation", step_res)
        self.assertIn("provenance_trace", step_res)
        self.assertEqual(step_res["provenance_trace"]["ablation_mode"], "B3")

    def test_pipeline_ablation_modes(self):
        sample = self.train_events[5]
        for mode in ["B0", "B1", "B2", "B3"]:
            res = self.pipeline.process_event(sample, ablation_mode=mode)
            self.assertEqual(res["ablation_mode"], mode)
            self.assertIn("recommended_action", res["recommendation"])

if __name__ == "__main__":
    unittest.main()

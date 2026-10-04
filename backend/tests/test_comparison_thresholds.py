"""Operational threshold contracts for the additional research comparison."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from comparison_audit import select_threshold
from audit_endpoints import strict_warning_metrics

class TestComparisonThresholds(unittest.TestCase):
    def test_select_new_warning_instead_of_persistent_earlier_alarm(self):
        episode={'times':np.arange(1,31)*60.,'onset':31*60.}
        p=np.zeros(30);p[23:]=.6;p[28:]=.7
        threshold=select_threshold(episode,p,5,20)
        self.assertEqual(threshold,.7)
        score=strict_warning_metrics(episode,p,5,threshold)
        self.assertEqual(score['strict_warning_recall'],1)
        self.assertEqual(score['strict_lead_minutes'],2)
        self.assertEqual(score['false_warning_episodes'],0)

    def test_zero_validation_budget_rejects_unavoidable_false_alarm(self):
        episode={'times':np.arange(1,31)*60.,'onset':31*60.}
        p=np.zeros(30);p[10]=.9;p[28:]=.8
        threshold=select_threshold(episode,p,5,0)
        self.assertGreater(threshold,.9)
        score=strict_warning_metrics(episode,p,5,threshold)
        self.assertEqual(score['strict_warning_recall'],0)
        self.assertEqual(score['false_warning_episodes'],0)

if __name__=='__main__':unittest.main()

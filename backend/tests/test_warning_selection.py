"""Selection constraints, profile timing, model readiness and inference work."""
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch,Mock
import hashlib
import json
import sys
import unittest
import sqlite3

import numpy as np
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'backend/research'))
from app.models.warning_policy import WarningPolicy,WarningConfig
from app.models.warning_profiles import profile_config
from app.routers import live_router as live
from select_warning_policy import choose_policy,guardrails
from streaming_forecast import ForecastStream
from app.ingestion.database import Database


class SelectionTests(unittest.TestCase):
    def test_fast_path_removes_mild_spike_without_delaying_stronger_validation_signal(self):
        times=np.arange(10)*60.;scores=np.zeros(10)
        scores[1]=.55;scores[8:]=.99
        choice=choose_policy(times,scores,600.,2,.5)
        self.assertTrue(choice['name'].startswith('fast_'))
        self.assertEqual(choice['validation_metrics']['false_notifications'],0)
        self.assertEqual(choice['validation_metrics']['notification_lead_minutes'],2.)
        self.assertFalse(guardrails(choice['validation_baseline'],choice['validation_metrics']))

    def test_without_timely_validation_signal_selection_preserves_immediate_profile(self):
        times=np.arange(10)*60.;scores=np.zeros(10);scores[1]=.6
        choice=choose_policy(times,scores,600.,2,.5)
        self.assertEqual(choice['name'],'immediate')

    def test_responsive_profile_exactly_preserves_original_spikes_and_first_crossings(self):
        scores=np.array([0,.8,0,.6,.7,0,0,.9])
        policy=WarningPolicy(profile_config('responsive'))
        result=[policy.update(i*60,float(p),.5) for i,p in enumerate(scores)]
        high=scores>=.5
        np.testing.assert_array_equal([r['warning'] for r in result],high)
        np.testing.assert_array_equal([r['notify'] for r in result],high&~np.r_[False,high[:-1]])

    def test_invalid_profiles_and_numeric_configuration_are_rejected(self):
        with self.assertRaises(ValueError):profile_config('best_everything')
        for config in ({'confirmations':1.5},{'cooldown_seconds':float('nan')},{'fast_ratio':.5},{'fast_ratio':float('inf')}):
            with self.assertRaises(ValueError):WarningConfig(**config)

    def test_unused_experts_keep_history_without_predicting(self):
        package={'experts':{key:dict(bundle=None,calibrators=[],threshold=.5) for key in ('aminer','wazuh','aminer+wazuh')}}
        def make_expert(*_):
            expert=Mock();expert.predict.return_value=np.array([.1,.2,.3,.4,.5,.6]);expert.counts=[1]
            return expert
        with patch('streaming_forecast.ExpertStream',side_effect=make_expert):stream=ForecastStream(package)
        stream.step(60,{}, {'aminer','wazuh'})
        stream.experts['aminer'].advance.assert_called_once()
        stream.experts['wazuh'].advance.assert_called_once()
        stream.experts['aminer'].predict.assert_not_called()
        stream.experts['wazuh'].predict.assert_not_called()
        stream.experts['aminer+wazuh'].predict.assert_called_once()
        stream.step(120,{}, {'aminer'})
        self.assertEqual(stream.experts['aminer'].advance.call_count,2)
        stream.experts['aminer'].predict.assert_called_once()

    def test_corrupt_or_unloadable_model_is_not_reported_ready(self):
        with TemporaryDirectory() as folder,patch.object(live,'MODEL',Path(folder)/'model.pkl'):
            self.assertFalse(live.status()['model_ready'])
            live.MODEL.write_bytes(b'corrupt')
            live.MODEL.with_suffix('.json').write_text(json.dumps({'sha256':'incorrect'}))
            self.assertFalse(live.status()['model_ready'])
            live.MODEL.with_suffix('.json').write_text(json.dumps({'sha256':hashlib.sha256(b'corrupt').hexdigest()}))
            self.assertFalse(live.status()['model_ready'])
            with self.assertRaises(HTTPException):live.model_package()

    def test_database_connection_closes_after_success_and_error(self):
        with TemporaryDirectory() as folder:
            db=Database(Path(folder)/'events.sqlite3')
            with db.connection() as connection:connection.execute('SELECT 1')
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            with self.assertRaises(RuntimeError):
                with db.connection() as failed:raise RuntimeError('fixture failure')
            with self.assertRaises(sqlite3.ProgrammingError):failed.execute('SELECT 1')
            db.save_experiment_result('fixture',{'value':1})
            self.assertEqual(db.get_experiment_result('fixture'),{'value':1})


if __name__=='__main__':unittest.main()

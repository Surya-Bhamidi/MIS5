"""Contracts for notification suppression, missing evidence and response receipts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sys
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'backend/research'))
from app.models.warning_policy import WarningPolicy,WarningConfig
from app.routers import live_router as live
from streaming_forecast import ForecastStream


class WarningTests(unittest.TestCase):
    def test_single_spike_suppressed_and_sustained_warning_notified_once(self):
        policy=WarningPolicy()
        output=[policy.update(i*60,p,.5) for i,p in enumerate([0,.9,0,.8,.9,.9,.9])]
        self.assertEqual([i for i,r in enumerate(output) if r['notify']],[4])
        self.assertFalse(output[1]['warning'])

    def test_hysteresis_and_cooldown_prevent_chatter(self):
        policy=WarningPolicy()
        output=[policy.update(i*60,p,.5) for i,p in enumerate([.8,.8,.49,.51,.3,.3,.9,.9,.9])]
        self.assertEqual([i for i,r in enumerate(output) if r['notify']],[1,7])
        self.assertTrue(output[2]['warning'])
        self.assertFalse(output[5]['warning'])

    def test_outage_and_context_change_cannot_complete_old_confirmation(self):
        policy=WarningPolicy()
        policy.update(0,.9,.5,'full')
        self.assertFalse(policy.update(60,.9,.5,'partial')['notify'])
        self.assertFalse(policy.update(120,None,.5,'none')['warning'])
        self.assertFalse(policy.update(180,.9,.5,'full')['notify'])
        self.assertFalse(policy.update(360,.9,.5,'full')['notify'])

    def test_invalid_time_or_probability_does_not_advance_state(self):
        policy=WarningPolicy()
        policy.update(60,.5,.5)
        for timestamp,p in [(60,.9),(30,.9),(120,float('nan')),(120,1.1)]:
            with self.assertRaises(ValueError):policy.update(timestamp,p,.5)
        self.assertTrue(policy.update(120,.9,.5)['notify'])

    def test_hysteresis_band_cannot_latch_warning_indefinitely(self):
        policy=WarningPolicy()
        output=[policy.update(i*60,p,.5) for i,p in enumerate([.9,.9,.45,.45,.45,.45,.45])]
        self.assertTrue(output[3]['warning'])
        self.assertFalse(any(r['warning'] for r in output[4:]))

    def test_cooldown_does_not_hide_confirmed_warning(self):
        policy=WarningPolicy()
        output=[policy.update(i*60,p,.5) for i,p in enumerate([.9,.9,.1,.1,.9,.9,.9])]
        self.assertTrue(output[5]['warning'])
        self.assertTrue(output[5]['episode_start'])
        self.assertFalse(output[5]['notify'])
        self.assertEqual(output[5]['reason'],'notification_cooldown')
        self.assertTrue(output[6]['notify'])
        self.assertFalse(output[6]['episode_start'])


class FakeForecast:
    def __init__(self,*_):self.last_time=None
    def checkpoint(self):return self.last_time
    def restore(self,checkpoint):self.last_time=checkpoint
    def step(self,timestamp,counts,healthy):
        self.last_time=timestamp
        key='+'.join(sorted(healthy)) or 'none'
        return dict(status='ok' if healthy else 'insufficient_sensors',available=key,
                    risk=[.8]*6 if healthy else None,threshold=.5 if healthy else None,
                    recommended_action='Restrict' if healthy else None,accepted_counts=counts)


class LiveApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_patch=patch.object(live,'DB',Path(self.temp.name)/'telemetry.sqlite3')
        self.db_patch.start();self.addCleanup(self.db_patch.stop)
        self.model_patch=patch.object(live,'model_package',return_value={'test':'fixture','scope':'test'})
        self.model_patch.start();self.addCleanup(self.model_patch.stop)
        self.forecast_patch=patch('streaming_forecast.ForecastStream',FakeForecast)
        self.forecast_patch.start();self.addCleanup(self.forecast_patch.stop)
        live.streams.clear()
        app=FastAPI();app.include_router(live.router)
        self.client=TestClient(app)
        self.stream=self.client.post('/api/live/streams',json={'mode':'replay','warning_profile':'confirmed'}).json()['stream_id']

    def observe(self,timestamp,**kwargs):
        return self.client.post(f'/api/live/streams/{self.stream}/observations',json=dict(timestamp=timestamp,counts={},heartbeats={'aminer':timestamp},**kwargs))

    def test_zero_counts_are_healthy_but_absent_or_expired_heartbeats_abstain(self):
        self.assertEqual(self.observe(60).json()['status'],'ok')
        for timestamp,heartbeats in [(120,{}),(240,{'aminer':60})]:
            data=self.client.post(f'/api/live/streams/{self.stream}/observations',json=dict(timestamp=timestamp,counts={'aminer:x':999},heartbeats=heartbeats)).json()
            self.assertEqual(data['status'],'insufficient_sensors')
            self.assertEqual(data['accepted_counts'],{})
            self.assertIsNone(data['recommended_action'])

    def test_bad_bucket_rejected_without_corrupting_temporal_state(self):
        self.observe(60)
        self.assertTrue(self.observe(60).json()['idempotent_replay'])
        for timestamp in (59,90):self.assertEqual(self.observe(timestamp).status_code,422)
        self.assertTrue(self.observe(120).json()['notify'])

    def test_default_stream_does_not_add_confirmation_or_cooldown_delay(self):
        created=self.client.post('/api/live/streams',json={'mode':'replay'}).json()
        self.assertEqual(created['warning_profile'],'responsive')
        data=self.client.post(f"/api/live/streams/{created['stream_id']}/observations",json=dict(
            timestamp=60,counts={},heartbeats={'aminer':60})).json()
        self.assertTrue(data['notify'])
        self.assertTrue(data['threshold_crossed'])
        self.assertEqual(data['warning_profile'],'responsive')

    def test_stale_sensor_counts_are_ignored_during_partial_outage(self):
        response=self.client.post(f'/api/live/streams/{self.stream}/observations',json=dict(
            timestamp=240,counts={'aminer:x':1,'wazuh:x':999},heartbeats={'aminer':240,'wazuh':60})).json()
        self.assertEqual(response['available'],'aminer')
        self.assertEqual(response['accepted_counts'],{'aminer:x':1})

    def test_notification_receipts_are_persistent_idempotent_and_final(self):
        self.observe(60)
        data=self.observe(120).json()
        identifier=data['notification_id']
        with live.database() as db:
            payload=json.loads(db.execute('SELECT payload FROM warnings WHERE id=?',(identifier,)).fetchone()[0])
        self.assertEqual(payload['observation_timestamp'],120)
        self.assertEqual(payload['stream_mode'],'replay')
        self.assertIsNone(payload['bucket_to_notification_ms'])
        path=f'/api/live/notifications/{identifier}/response'
        first=self.client.post(path,json={'status':'acknowledged'}).json()
        again=self.client.post(path,json={'status':'acknowledged'}).json()
        self.assertEqual(first['acknowledgment_latency_ms'],again['acknowledgment_latency_ms'])
        self.assertGreaterEqual(first['acknowledgment_latency_ms'],0)
        self.assertIsNone(first['completion_latency_ms'])
        self.assertIsNotNone(self.client.post(path,json={'status':'completed'}).json()['completion_latency_ms'])
        self.assertEqual(self.client.post(path,json={'status':'failed'}).status_code,409)
        live.streams.clear()
        self.assertEqual(self.client.post(path,json={'status':'completed'}).status_code,200)

    def test_malformed_evidence_is_rejected(self):
        for counts,heartbeats in [({'other:x':1},{}),({'aminer:x':-1},{}),({}, {'aminer':121}),({'aminer:x':1e308,'aminer:y':1e308},{})]:
            response=self.client.post(f'/api/live/streams/{self.stream}/observations',json=dict(timestamp=120,counts=counts,heartbeats=heartbeats))
            self.assertEqual(response.status_code,422)

    def test_future_live_bucket_is_rejected_without_advancing_state(self):
        identifier=self.client.post('/api/live/streams',json={'mode':'live','warning_profile':'confirmed'}).json()['stream_id']
        with patch.object(live.time,'time',return_value=1000):
            live.streams[identifier]['touched']=1000
            for timestamp in (1002,1120):
                response=self.client.post(f'/api/live/streams/{identifier}/observations',json=dict(timestamp=timestamp,counts={},heartbeats={'aminer':timestamp}))
                self.assertEqual(response.status_code,422)
            self.assertIsNone(live.streams[identifier]['forecast'].last_time)

    def test_live_bucket_age_is_recorded_without_claiming_sensor_latency(self):
        identifier=self.client.post('/api/live/streams',json={'mode':'live','warning_profile':'confirmed'}).json()['stream_id']
        with patch.object(live.time,'time',return_value=1000):
            live.streams[identifier]['touched']=1000
            for timestamp in (900,960):
                data=self.client.post(f'/api/live/streams/{identifier}/observations',json=dict(timestamp=timestamp,counts={},heartbeats={'aminer':timestamp})).json()
            self.assertTrue(data['notify'])
            self.assertEqual(data['bucket_to_notification_ms'],40000)
            with live.database() as db:
                payload=json.loads(db.execute('SELECT payload FROM warnings WHERE id=?',(data['notification_id'],)).fetchone()[0])
            self.assertEqual(payload['received_at'],1000)
            self.assertEqual(payload['observation_timestamp'],960)
            self.assertEqual(payload['bucket_to_notification_ms'],40000)

    def test_sessions_are_isolated_and_can_be_closed(self):
        self.observe(60)
        other=self.client.post('/api/live/streams',json={'mode':'replay','warning_profile':'confirmed'}).json()['stream_id']
        data=self.client.post(f'/api/live/streams/{other}/observations',json=dict(timestamp=60,counts={},heartbeats={'aminer':60})).json()
        self.assertFalse(data['notify'])
        self.assertEqual(self.client.delete(f'/api/live/streams/{other}').status_code,200)
        self.assertEqual(self.client.delete(f'/api/live/streams/{other}').status_code,404)


class StreamingTests(unittest.TestCase):
    def test_incremental_forecast_matches_batch_beyond_trailing_window(self):
        import robust_forecasting as robust
        import selective_fusion as selective
        from threadpoolctl import threadpool_limits
        episodes={}
        for i,name in enumerate('abcd'):
            counts=np.zeros((90,1));counts[25+i:,0]=1;counts[55+i:,0]=4
            episodes[name]=dict(counts=counts,times=np.arange(90)*60.,onset=70*60.,
                                truth=np.r_[np.zeros(50,dtype=int),np.ones(40,dtype=int)],names=np.array(['aminer:x']))
        with threadpool_limits(limits=1):
            _,bundle,_=robust.fit_predict(episodes,list('abc'),['d'],['aminer'])
            calibrators=[dict(slope=1.,intercept=0.,constant_prior=None) for _ in range(6)]
            package={'experts':{'aminer':dict(bundle=bundle,calibrators=calibrators,threshold=.5)}}
            stream=ForecastStream(package)
            risks=[stream.step(i*60,{'aminer:x':float(row[0])},{'aminer'})['risk'] for i,row in enumerate(episodes['d']['counts'])]
            batch=selective.predict_current(bundle,episodes['d'],['aminer'],{'pooled_fixed_blend':calibrators})['risk']
            np.testing.assert_allclose(risks,batch,atol=1e-10,rtol=0)
            self.assertEqual(len(stream.experts['aminer'].counts),60)
            self.assertIsNone(stream.step(90*60,{},set())['risk'])
            recovered=stream.step(91*60,{}, {'aminer'})
            self.assertEqual(recovered['history_minutes'],1)
            fresh=ForecastStream(package).step(91*60,{}, {'aminer'})
            np.testing.assert_array_equal(recovered['risk'],fresh['risk'])
            previous=stream.last_time
            for timestamp,healthy in [(previous,{'aminer'}),(previous+30,{'aminer'}),(float('nan'),{'aminer'}),(previous+60,{'wazuh'})]:
                with self.assertRaises(ValueError):stream.step(timestamp,{},healthy)
                self.assertEqual(stream.last_time,previous)
                self.assertEqual(len(stream.experts['aminer'].counts),1)
            after_gap=stream.step(previous+120,{}, {'aminer'})
            self.assertEqual(after_gap['history_minutes'],1)
            np.testing.assert_array_equal(after_gap['risk'],fresh['risk'])


if __name__=='__main__':unittest.main()

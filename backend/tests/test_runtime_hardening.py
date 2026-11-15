"""Local adversarial inputs and operation faults; all writes use temporary databases."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import logging
import pickle
import sqlite3
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
import asyncio
from threading import RLock

from fastapi.testclient import TestClient
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'backend/research'))
from app.main import app
from app.config import THREAT_STATES
from app.ingestion.database import Database
from app.ingestion.synthetic_generator import SyntheticEventGenerator
from app.models.pipeline import CyberPipeline
from app.models.decision_network import ResponseDecisionNetwork
from app.models.onset_decision import onset_losses,ACTIONS
from app.request_safety import LocalRequestGuard
from app.evaluation.serialization import serialized
from app.routers import scenarios,pipeline_router,live_router as live
import test_operational_improvements as fixtures
FakeForecast=fixtures.FakeForecast

logging.getLogger('httpx').setLevel(logging.WARNING)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.db=Database(Path(self.folder.name)/'events.sqlite3')
        self.events=SyntheticEventGenerator(noise_rate=0,missing_alert_rate=0,seed=9).generate_sequence(12)
        self.db.insert_events('events_synthetic',[dict(e) for e in self.events],run_id='first')
        self.db.insert_events('events_synthetic',[dict(e) for e in self.events],run_id='second')
        self.pipeline=CyberPipeline(bn=pipeline_router.pipeline.bn,hmm=pipeline_router.pipeline.hmm)
        for target,name,value in [(scenarios,'db',self.db),(pipeline_router,'db',self.db),(pipeline_router,'pipeline',self.pipeline),
                                  (live,'DB',Path(self.folder.name)/'live.sqlite3')]:
            item=patch.object(target,name,value);item.start();self.addCleanup(item.stop)
        live.streams.clear()
        pipeline_router.contexts.clear()
        self.client=TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',50000),raise_server_exceptions=False)

    def test_batch_rejects_untrusted_table_identifiers_and_unbounded_work(self):
        for body in [dict(scenario_id='experiment_results'),dict(scenario_id='events_synthetic --'),
                     dict(scenario_id='events_synthetic',limit=-1),dict(scenario_id='events_synthetic',limit=100000),
                     dict(scenario_id='events_synthetic',ablation_mode='unknown')]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/api/pipeline/batch',json=body).status_code,422)
        self.assertEqual(self.pipeline.step_counter,0)

    def test_blank_synthetic_run_cannot_delete_other_runs(self):
        count=self.db.get_event_count('events_synthetic')
        response=self.client.post('/api/scenarios/synthetic/generate',json=dict(run_id='',n_steps=10))
        self.assertEqual(response.status_code,422)
        self.assertEqual(self.db.get_event_count('events_synthetic'),count)

    def test_synthetic_generation_parameters_have_finite_bounds(self):
        # Prove rejection without actually allocating an oversized sequence if
        # the vulnerable endpoint accepts the requested work count.
        with patch.object(scenarios.SyntheticEventGenerator,'generate_sequence',return_value=self.events):
            for body in (dict(n_steps=-1),dict(n_steps=10000000),dict(noise_rate=-.1),dict(missing_alert_rate=1.01)):
                with self.subTest(body=body):self.assertEqual(self.client.post('/api/scenarios/synthetic/generate',json=body).status_code,422)

    def test_empty_or_invalid_beliefs_and_baseline_actions_are_rejected(self):
        for belief,baseline in [({},'Monitor'),({'unknown':1},'Monitor'),({'Benign':-1,'Recon':2},'Monitor'),({'Benign':.2},'Monitor'),({'Benign':1},'unknown')]:
            response=self.client.post('/api/simulation/what-if',json=dict(current_belief=belief,hypothetical_action='Block',baseline_action=baseline))
            self.assertEqual(response.status_code,422)

    def test_invalid_alert_never_poison_temporal_state(self):
        for alert in ({'timestamp':'not-a-time'},{'timestamp':1,'dst_ip':[]},{'timestamp':1,'signature_category':[]},{}):
            with self.subTest(alert=alert):self.assertEqual(self.client.post('/api/pipeline/infer',json={'alert':alert}).status_code,422)
        self.assertEqual(self.pipeline.step_counter,0)

    def test_external_browser_origin_and_host_cannot_mutate_local_state(self):
        response=self.client.post('/api/pipeline/reset',headers={'Origin':'https://untrusted.invalid'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.get('/api/health',headers={'Host':'untrusted.invalid'}).status_code,400)
        allowed=self.client.get('/api/health',headers={'Origin':'http://localhost:5173'})
        self.assertEqual(allowed.status_code,200)
        self.assertEqual(allowed.headers.get('access-control-allow-origin'),'http://localhost:5173')

    def test_nonfinite_json_and_secret_like_rejected_values_are_not_reflected(self):
        with patch.object(live,'model_package',return_value={'test':'fixture','scope':'test'}),patch('streaming_forecast.ForecastStream',FakeForecast):
            stream=self.client.post('/api/live/streams',json={'mode':'replay'}).json()['stream_id']
        for literal in ('NaN','Infinity','-Infinity'):
            response=self.client.post(f'/api/live/streams/{stream}/observations',content='{"timestamp":'+literal+',"counts":{},"heartbeats":{}}',headers={'Content-Type':'application/json'})
            self.assertEqual(response.status_code,422)
        sentinel='private-fixture-value-do-not-reflect'
        response=self.client.post('/api/live/streams',json={'unexpected':sentinel})
        self.assertEqual(response.status_code,422)
        self.assertNotIn(sentinel,response.text)

    def test_oversized_request_stops_before_json_validation(self):
        response=self.client.post('/api/live/streams',content=b'x'*(2*1024*1024+1),headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,413)

    def test_loopback_boundary_rejects_remote_peer_even_with_spoofed_headers(self):
        remote=TestClient(app,base_url='http://127.0.0.1',client=('198.51.100.9',50000))
        self.assertEqual(remote.get('/api/health',headers={'X-Forwarded-For':'127.0.0.1','Origin':'http://localhost:5173'}).status_code,403)
        self.assertEqual(self.client.get('/api/health',headers={'Sec-Fetch-Site':'cross-site'}).status_code,403)

    def test_legacy_batch_replay_is_causal_and_does_not_reset_other_state(self):
        event=dict(self.events[0]);self.pipeline.process_event(event)
        self.assertEqual(self.client.post('/api/pipeline/infer',json={'alert':event}).status_code,200)
        before=self.pipeline.step_counter
        first=self.client.post('/api/pipeline/batch',json=dict(scenario_id='events_synthetic',run_id='first',limit=7)).json()
        second=self.client.post('/api/pipeline/batch',json=dict(scenario_id='events_synthetic',run_id='first',limit=2)).json()
        self.assertEqual(len(first['steps']),7)
        self.assertEqual(first['steps'][:2],second['steps'])
        self.assertEqual(self.pipeline.step_counter,before)
        earlier={**event,'timestamp':event['timestamp']-1}
        self.assertEqual(self.client.post('/api/pipeline/infer',json={'alert':earlier}).status_code,409)
        self.assertEqual(self.pipeline.step_counter,before)

    def test_legacy_clients_have_independent_temporal_histories_and_resets(self):
        first=dict(self.events[0]);next_event=dict(self.events[1])
        peer=TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',50001))
        a=self.client.post('/api/pipeline/infer',json={'alert':first}).json()
        b=peer.post('/api/pipeline/infer',json={'alert':first}).json()
        self.assertEqual(a,b)
        peer.post('/api/pipeline/reset')
        second=self.client.post('/api/pipeline/infer',json={'alert':next_event}).json()
        self.assertEqual(second['step'],2)
        self.assertEqual(peer.post('/api/pipeline/infer',json={'alert':first}).json()['step'],1)

    def test_seeded_malformed_observations_and_paths_do_not_crash_or_advance(self):
        with patch.object(live,'model_package',return_value={'test':'fixture','scope':'test'}),patch('streaming_forecast.ForecastStream',FakeForecast):
            identifier=self.client.post('/api/live/streams',json={'mode':'replay'}).json()['stream_id']
        base=dict(timestamp=60,counts={},heartbeats={'aminer':60})
        bad=[{**base,'counts':v} for v in (None,[],{'aminer:x':-1},{'aminer:x':'1'},{'aminer:x':True},{'aminer:':1},{'unknown:x':1})]
        bad += [{**base,'heartbeats':v} for v in (None,[],{'aminer':61},{'unknown':60},{'aminer':'60'})]
        bad += [{**base,'truth':1},{**base,'onset':300},{**base,'recommended_action':'Isolate'},{**base,'timestamp':True}]
        for payload in bad:
            self.assertEqual(self.client.post(f'/api/live/streams/{identifier}/observations',json=payload).status_code,422)
        self.assertIsNone(live.streams[identifier]['forecast'].last_time)
        for name in ('unknown','config.json','..%2F..%2FREADME.md'):
            self.assertEqual(self.client.get('/api/research/assets/'+name).status_code,404)


class LiveFailureTests(unittest.TestCase):
    setUp=fixtures.LiveApiTests.setUp
    observe=fixtures.LiveApiTests.observe

    def test_exact_retry_is_idempotent_but_same_time_changed_input_conflicts(self):
        self.observe(60);first=self.observe(120).json()
        second=self.observe(120)
        self.assertEqual(second.status_code,200)
        self.assertEqual(second.json()['notification_id'],first['notification_id'])
        self.assertTrue(second.json()['idempotent_replay'])
        changed=self.client.post(f'/api/live/streams/{self.stream}/observations',json=dict(timestamp=120,counts={'aminer:x':1},heartbeats={'aminer':120}))
        self.assertEqual(changed.status_code,409)
        with live.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM warnings').fetchone()[0],1)

    def test_storage_failure_rolls_back_forecast_and_warning_before_retry(self):
        self.observe(60)
        with patch.object(live,'database',side_effect=sqlite3.OperationalError('fixture unavailable')):
            response=self.client.post(f'/api/live/streams/{self.stream}/observations',json=dict(timestamp=120,counts={},heartbeats={'aminer':120}))
        self.assertEqual(response.status_code,503)
        self.assertEqual(live.streams[self.stream]['forecast'].last_time,60)
        retried=self.observe(120)
        self.assertEqual(retried.status_code,200)
        self.assertTrue(retried.json()['notify'])

    def test_final_response_receipt_is_immutable_on_duplicate(self):
        self.observe(60);data=self.observe(120).json();identifier=data['notification_id']
        path=f'/api/live/notifications/{identifier}/response'
        self.client.post(path,json={'status':'completed','note':'first receipt'})
        self.client.post(path,json={'status':'completed','note':'replacement must not overwrite'})
        with live.database() as db:note=db.execute('SELECT note FROM warnings WHERE id=?',(identifier,)).fetchone()[0]
        self.assertEqual(note,'first receipt')

    def test_concurrent_identical_retries_commit_once(self):
        self.observe(60)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.observe(120),range(4)))
        self.assertTrue(all(r.status_code==200 for r in results))
        self.assertEqual(len({r.json()['notification_id'] for r in results}),1)
        self.assertEqual(sum(r.json()['idempotent_replay'] for r in results),3)
        with live.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM warnings').fetchone()[0],1)

    def test_inference_error_restores_state_and_failed_receipt_has_resolution_time(self):
        self.observe(60)
        def broken(forecast,timestamp,*_):forecast.last_time=timestamp;raise ValueError('controlled failure')
        with patch.object(FakeForecast,'step',broken):
            self.assertEqual(self.observe(120).status_code,503)
        self.assertEqual(live.streams[self.stream]['forecast'].last_time,60)
        notification=self.observe(120).json()['notification_id']
        response=self.client.post(f'/api/live/notifications/{notification}/response',json={'status':'failed'}).json()
        self.assertIsNotNone(response['resolution_latency_ms'])
        self.assertIsNone(response['completion_latency_ms'])

    def test_stream_limit_is_bounded_and_expired_slots_are_reclaimed(self):
        for _ in range(31):self.assertEqual(self.client.post('/api/live/streams',json={'mode':'replay'}).status_code,200)
        self.assertEqual(self.client.post('/api/live/streams',json={'mode':'replay'}).status_code,429)
        live.streams[self.stream]['touched']-=3601
        self.assertEqual(self.client.post('/api/live/streams',json={'mode':'replay'}).status_code,200)
        self.assertEqual(len(live.streams),32)

    def test_backwards_clock_does_not_record_negative_receipt_latency(self):
        self.observe(60);identifier=self.observe(120).json()['notification_id']
        with patch.object(live.time,'time',return_value=1.):
            response=self.client.post(f'/api/live/notifications/{identifier}/response',json={'status':'acknowledged'})
        self.assertEqual(response.status_code,409)


class SemanticTests(unittest.TestCase):
    def test_same_what_if_action_has_identical_trajectories_and_zero_benefit(self):
        model=ResponseDecisionNetwork()
        for action in model.actions:
            result=model.simulate_what_if({'Compromise':1.},action,action)
            self.assertEqual(result['loss_trajectories']['hypothetical'],result['loss_trajectories']['baseline'])
            self.assertEqual(result['net_loss_prevented'],0)

    def test_rule_signature_does_not_depend_on_numeric_port(self):
        pipeline=CyberPipeline()
        result=pipeline._rule_based_baseline({'dst_port':''},{'signature_category':'DDOS_FLOOD'})
        self.assertEqual(result['recommended_action'],'Isolate')

    def test_partial_but_loadable_package_cannot_report_ready(self):
        keys=('aminer','suricata','wazuh','aminer+suricata','aminer+wazuh','suricata+wazuh','aminer+suricata+wazuh')
        with TemporaryDirectory() as folder,patch.object(live,'MODEL',Path(folder)/'model.pkl'):
            content=pickle.dumps({'version':1,'experts':{k:{} for k in keys}})
            live.MODEL.write_bytes(content);live.MODEL.with_suffix('.json').write_text(json.dumps({'sha256':hashlib.sha256(content).hexdigest()}))
            self.assertFalse(live.status()['model_ready'])

    def test_database_rejects_untrusted_identifiers_and_does_not_mutate_event_inputs(self):
        with TemporaryDirectory() as folder:
            db=Database(Path(folder)/'events.sqlite3')
            for name in ('experiment_results','events_synthetic --','events_lldos1 WHERE 1=1'):
                with self.assertRaises(ValueError):db.get_events(name)
            events=SyntheticEventGenerator(seed=12).generate_sequence(4)
            original=[dict(e) for e in events]
            db.insert_events('events_synthetic',events,run_id='fixture')
            self.assertEqual(events,original)

    def test_empty_generation_replaces_only_its_own_run_and_quoted_ids_are_data(self):
        with TemporaryDirectory() as folder:
            db=Database(Path(folder)/'events.sqlite3');events=SyntheticEventGenerator(seed=21).generate_sequence(8)
            for name in ('first',"quoted' OR 1=1 --"):
                db.insert_events('events_synthetic',events,run_id=name)
            db.insert_events('events_synthetic',[],run_id='first')
            self.assertEqual(db.get_event_count('events_synthetic',run_id='first'),0)
            self.assertEqual(db.get_event_count('events_synthetic',run_id="quoted' OR 1=1 --"),len(events))

    def test_legacy_prior_trace_and_bounded_history_are_truthful(self):
        pipeline=CyberPipeline(bn=pipeline_router.pipeline.bn,hmm=pipeline_router.pipeline.hmm)
        event=SyntheticEventGenerator(seed=10).generate_sequence(1)[0]
        prior=THREAT_STATES[int(np.argmax(pipeline.current_hmm_belief))]
        output=pipeline.process_event({**event,'signature_category':'DDOS_FLOOD'})
        self.assertEqual(output['provenance_trace']['hmm_transition']['prior_dominant_state'],prior)
        for i in range(100):pipeline.process_event({**event,'timestamp':event['timestamp']+i+1})
        self.assertLessEqual(len(pipeline.history_observations),15)
        self.assertLessEqual(len(pipeline.history_events),30)

    def test_utility_selection_uses_unrounded_values_and_seeded_argmax(self):
        matrix={'Benign':dict(Monitor=1.00001,Restrict=1.00002,Block=0.,Isolate=-1.)}
        self.assertEqual(ResponseDecisionNetwork(matrix).evaluate_actions({'Benign':1})['recommended_action'],'Restrict')
        model=ResponseDecisionNetwork();rng=np.random.default_rng(57)
        for values in rng.dirichlet(np.ones(6),size=200):
            belief=dict(zip(THREAT_STATES,values));actual=model.evaluate_actions(belief)
            expected={a:sum(belief[s]*model.utilities[s][a] for s in THREAT_STATES) for a in model.actions}
            self.assertEqual(actual['recommended_action'],max(expected,key=expected.get))

    def test_age_aware_onset_decisions_are_minimal_and_never_optimistically_improve_with_age(self):
        rng=np.random.default_rng(13)
        for _ in range(200):
            risk=np.sort(rng.uniform(0,1,6))
            old=onset_losses(risk,0);aged=onset_losses(risk,120)
            self.assertTrue(np.all(aged>=old-1e-12))
            reference=[]
            for _,delay,effect,disruption in ACTIONS:
                deadline=delay+2;clock=(0,1,2,5,10,15,30);cdf=np.r_[0.,risk]
                upper=next((j for j,t in enumerate(clock) if t>=deadline),6)
                if upper==0:late=0.
                else:
                    fraction=(deadline-clock[upper-1])/(clock[upper]-clock[upper-1])
                    late=cdf[upper-1]+fraction*(cdf[upper]-cdf[upper-1])
                reference.append(disruption+20*(risk[-1]-.8*effect*max(0.,risk[-1]-late)))
            np.testing.assert_allclose(aged,reference,atol=1e-12,rtol=0)
            self.assertEqual(int(onset_losses(risk,1900).argmin()),0)

    def test_chunked_and_slow_bodies_are_bounded_before_endpoint(self):
        async def check(slow):
            messages=[];called=[];index=0
            async def endpoint(*_):called.append(True)
            async def receive():
                nonlocal index
                if slow:await asyncio.sleep(.02)
                index+=1
                return {'type':'http.request','body':b'x'*700000,'more_body':index<4}
            async def send(message):messages.append(message)
            scope={'type':'http','path':'/api/live/streams','method':'POST','headers':[],'client':('127.0.0.1',42)}
            real=asyncio.timeout
            if slow:
                with patch('app.request_safety.asyncio.timeout',side_effect=lambda _:real(.005)):
                    await LocalRequestGuard(endpoint)(scope,receive,send)
            else:await LocalRequestGuard(endpoint)(scope,receive,send)
            self.assertFalse(called)
            self.assertEqual(messages[0]['status'],408 if slow else 413)
        asyncio.run(check(False));asyncio.run(check(True))

    def test_serialized_legacy_evaluations_do_not_interleave(self):
        import time
        active=0;maximum=0;lock=RLock()
        @serialized(lock)
        def operation():
            nonlocal active,maximum
            active+=1;maximum=max(maximum,active);time.sleep(.002);active-=1
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:operation(),range(8)))
        self.assertEqual(maximum,1)


if __name__=='__main__':unittest.main()

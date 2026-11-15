"""Local shadow-mode telemetry API. Recommendations never execute defenses."""
from functools import lru_cache
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Literal
import hashlib
import json
import math
import pickle
import sqlite3
import sys
import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator,field_validator
from threadpoolctl import threadpool_limits

from app.models.warning_policy import WarningPolicy
from app.models.warning_profiles import PROFILES,profile_config
from app.models.package_validation import validate_package
from app.models.onset_decision import onset_losses,ACTIONS
from app.artifact_store import read_json

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT/'data/research/live/model.pkl'
DB = ROOT/'data/research/live/telemetry.sqlite3'
SENSORS = {'aminer','suricata','wazuh'}
router = APIRouter(prefix='/api/live',tags=['Streaming shadow evaluation'])
lock = RLock()
streams = {}


class StreamRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['live','replay'] = 'live'
    warning_profile: Literal['responsive','confirmed'] = 'responsive'


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    timestamp: float = Field(allow_inf_nan=False,strict=True)
    counts: dict[str,float] = Field(max_length=4096)
    heartbeats: dict[str,float] = Field(max_length=3)

    @field_validator('counts','heartbeats',mode='before')
    @classmethod
    def numeric_values(cls,value):
        if isinstance(value,dict) and any(not isinstance(v,(int,float)) or isinstance(v,bool) for v in value.values()):
            raise ValueError('Counts and heartbeat values must be JSON numbers')
        return value

    @model_validator(mode='after')
    def validate_evidence(self):
        for token,value in self.counts.items():
            if len(token)>256 or ':' not in token or not token.partition(':')[2].strip() or token.split(':')[0] not in SENSORS:
                raise ValueError('Detector names must have a supported sensor:detector prefix')
            if not math.isfinite(value) or value<0:raise ValueError('Counts must be finite and nonnegative')
        try:
            total = math.fsum(self.counts.values())
        except OverflowError:
            raise ValueError('Total detector counts exceed the supported numeric range')
        if not math.isfinite(total):raise ValueError('Total detector counts must be finite')
        for sensor,timestamp in self.heartbeats.items():
            if sensor not in SENSORS or not math.isfinite(timestamp) or timestamp>self.timestamp:
                raise ValueError('Invalid sensor heartbeat')
        return self


class ResponseReceipt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status: Literal['acknowledged','completed','failed']
    note: str = Field(default='',max_length=1000)


def checked_model_bytes():
    if not MODEL.is_file() or not MODEL.with_suffix('.json').is_file():
        raise HTTPException(503,'Prepare the local model with python backend/research/prepare_live_model.py')
    try:
        content = MODEL.read_bytes()
        manifest = json.loads(MODEL.with_suffix('.json').read_text())
        if hashlib.sha256(content).hexdigest()!=manifest['sha256']:
            raise HTTPException(503,'Local model checksum mismatch; rebuild the model package')
    except (OSError,ValueError,KeyError,TypeError):
        raise HTTPException(503,'Local model manifest is invalid or unreadable; rebuild the model package')
    return content


@lru_cache(maxsize=1)
def decoded_package(content):
    # This path is fixed and generated locally; no uploaded pickle is accepted.
    try:
        package=pickle.loads(content)
        return validate_package(package)
    except Exception as error:
        raise HTTPException(503,'Local model cannot be loaded; rebuild it in this environment') from error


def model_package():
    return decoded_package(checked_model_bytes())


@contextmanager
def database():
    DB.parent.mkdir(parents=True,exist_ok=True)
    connection = sqlite3.connect(DB)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS warnings (id TEXT PRIMARY KEY, stream TEXT, emitted REAL, payload TEXT, acknowledged REAL, completed REAL, status TEXT, note TEXT, resolved REAL)')
        if 'resolved' not in {r[1] for r in connection.execute('PRAGMA table_info(warnings)')}:
            connection.execute('ALTER TABLE warnings ADD COLUMN resolved REAL')
        with connection:
            yield connection
    finally:
        connection.close()


@router.get('/status')
def status():
    try:
        model_package();ready=True;reason=None
    except HTTPException as error:
        ready=False;reason=error.detail
    return dict(model_ready=ready,model_error=reason,mode='shadow',horizons=[1,2,5,10,15,30],
                bucket_seconds=60,heartbeat_max_age_seconds=90,
                default_warning_profile='responsive',warning_profiles={name:asdict(config) for name,config in PROFILES.items()},
                scope='Local streaming recommendations and recorded response receipts; no automated defense')


@router.get('/report')
def report():
    path = ROOT/'experiments/operational_improvements/evaluation.json'
    if not path.is_file():raise HTTPException(503,'Run backend/research/evaluate_improvements.py')
    result = read_json(path.relative_to(ROOT))
    benchmark = path.with_name('live_benchmark.json')
    selection = path.with_name('selected_evaluation.json')
    return {**result,'default_warning_profile':'responsive',
            'candidate_evaluation':read_json(selection.relative_to(ROOT)) if selection.is_file() else None,
            'benchmark':read_json(benchmark.relative_to(ROOT)) if benchmark.is_file() else None}


@router.post('/streams')
def create_stream(request: StreamRequest):
    with lock:
        now = time.time()
        for key in list(streams):
            if now-streams[key]['touched']>3600:del streams[key]
        if len(streams)>=32:raise HTTPException(429,'Active stream limit reached; close an existing stream')
        sys.path.insert(0,str(ROOT/'backend/research')) if str(ROOT/'backend/research') not in sys.path else None
        from streaming_forecast import ForecastStream
        package = model_package()
        key = uuid.uuid4().hex
        config=profile_config(request.warning_profile)
        streams[key] = dict(forecast=ForecastStream(package),policy=WarningPolicy(config),touched=now,
                            mode=request.mode,warning_profile=request.warning_profile)
        return dict(stream_id=key,mode=request.mode,warning_profile=request.warning_profile,
                    warning_config=asdict(config),model_fold=package['test'],scope=package['scope'])


@router.delete('/streams/{stream_id}')
def close_stream(stream_id: str):
    with lock:
        if stream_id not in streams:raise HTTPException(404,'Unknown or expired stream')
        del streams[stream_id]
        return dict(status='closed')


@router.post('/streams/{stream_id}/observations')
def observe(stream_id: str, observation: Observation):
    received, started = time.time(),time.perf_counter()
    fingerprint=hashlib.sha256(json.dumps(observation.model_dump(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    with lock, threadpool_limits(limits=1):
        session = streams.get(stream_id)
        if session is None or received-session['touched']>3600:
            streams.pop(stream_id,None)
            raise HTTPException(404,'Unknown or expired stream')
        previous = session['forecast'].last_time
        if previous is not None and observation.timestamp==previous:
            if fingerprint==session.get('last_fingerprint'):
                session['touched']=received
                return {**session['last_response'],'idempotent_replay':True}
            raise HTTPException(409,'This observation timestamp was already committed with different evidence')
        if session['mode']=='live' and not -1 <= received-observation.timestamp <= 120:
            raise HTTPException(422,'Live buckets must be finalized in the past 120 seconds (1 second clock tolerance); use replay for historical input')
        delta = None if previous is None else observation.timestamp-previous
        if delta is not None and (delta<59.999 or not math.isclose(delta,round(delta/60)*60,abs_tol=.001,rel_tol=0)):
            raise HTTPException(422,'Provide ordered, nonduplicate one-minute buckets (gaps allowed)')
        healthy = {s for s,t in observation.heartbeats.items() if observation.timestamp-t<=90}
        valid_counts = {k:v for k,v in observation.counts.items() if k.split(':')[0] in healthy}
        checkpoint=session['forecast'].checkpoint();policy_state=session['policy'].__dict__.copy()
        try:
            result = session['forecast'].step(observation.timestamp,valid_counts,healthy)
            decision_time=time.time()
            age=max(0.,decision_time-observation.timestamp) if session['mode']=='live' else 0.
            if session['mode']=='live' and result['risk'] is not None:
                adjusted=onset_losses(result['risk'],age)
                result['modeled_losses']=adjusted.tolist()
                result['recommended_action']=ACTIONS[int(adjusted.argmin())][0]
            result['decision_age_seconds']=age
            result['decision_window_end']=observation.timestamp+1800
            result['decision_time_basis']='Receipt-time age; linearly interpolated onset CDF' if session['mode']=='live' else 'Historical observation time'
            result['warning_profile']=session['warning_profile']
            result['threshold_crossed']=result['risk'] is not None and result['risk'][-1]>=result['threshold']
            threshold = result['threshold'] if result['threshold'] is not None else 1.000001
            warning = session['policy'].update(observation.timestamp,None if result['risk'] is None else result['risk'][-1],threshold,result['available'])
            event_id = None;bucket_latency = None
            if warning['notify']:
                event_id = uuid.uuid4().hex;emitted = time.time()
                if session['mode']=='live' and emitted>=observation.timestamp:bucket_latency = (emitted-observation.timestamp)*1000
                payload = {**result,**warning,'observation_timestamp':observation.timestamp,
                           'received_at':received,'stream_mode':session['mode'],'bucket_to_notification_ms':bucket_latency}
                with database() as db:
                    db.execute('INSERT INTO warnings (id,stream,emitted,payload,status) VALUES (?,?,?,?,?)',
                               (event_id,stream_id,emitted,json.dumps(payload,allow_nan=False),'emitted'))
        except Exception as error:
            session['forecast'].restore(checkpoint)
            session['policy'].__dict__.clear();session['policy'].__dict__.update(policy_state)
            raise HTTPException(503,'Observation was not committed; retry the same bucket') from error
        response={**result,**warning,'notification_id':event_id,'timestamp':observation.timestamp,
                  'processing_latency_ms':(time.perf_counter()-started)*1000,'bucket_to_notification_ms':bucket_latency,
                  'observation_age_seconds':received-observation.timestamp if session['mode']=='live' else None,
                  'mode':session['mode'],'horizons':[1,2,5,10,15,30],'idempotent_replay':False}
        session.update(touched=received,last_fingerprint=fingerprint,last_response=response)
        return response


@router.post('/notifications/{notification_id}/response')
def record_response(notification_id: str, receipt: ResponseReceipt):
    now = time.time()
    with lock, database() as db:
        row = db.execute('SELECT emitted,acknowledged,completed,status,resolved FROM warnings WHERE id=?',(notification_id,)).fetchone()
        if row is None:raise HTTPException(404,'Unknown notification')
        emitted, acknowledged, completed, old_status, resolved = row
        resolved=resolved if resolved is not None else completed
        if old_status in ('completed','failed') and receipt.status!=old_status:
            raise HTTPException(409,'Response already finalized')
        duplicate=old_status==receipt.status and old_status in ('acknowledged','completed','failed')
        if not duplicate:
            if now<max(emitted,acknowledged or emitted):raise HTTPException(409,'Server clock moved backwards; receipt timing cannot be recorded reliably')
            acknowledged = acknowledged if acknowledged is not None else now
            if receipt.status=='completed':completed = now
            if receipt.status in ('completed','failed'):resolved=now
            db.execute('UPDATE warnings SET acknowledged=?,completed=?,status=?,note=?,resolved=? WHERE id=?',
                       (acknowledged,completed,receipt.status,receipt.note,resolved,notification_id))
        return dict(notification_id=notification_id,status=receipt.status,
                    acknowledgment_latency_ms=(acknowledged-emitted)*1000,
                    completion_latency_ms=None if completed is None else (completed-emitted)*1000,
                    resolution_latency_ms=None if resolved is None else (resolved-emitted)*1000,
                    scope='Caller-reported receipt timing; attack prevention is not inferred')

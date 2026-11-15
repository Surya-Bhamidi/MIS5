"""Bounded normalized input for the earlier demonstration API."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

Ablation=Literal['B0','B1','B2','B3']
Scenario=Literal['events_lldos1','events_lldos2','events_synthetic']


class LegacyAlert(BaseModel):
    model_config=ConfigDict(extra='forbid')
    timestamp: float=Field(allow_inf_nan=False,strict=True)
    signature_category: Literal['ICMP_SWEEP','RPC_DISCOVERY','EXPLOIT_PAYLOAD','REMOTE_SHELL','DDOS_FLOOD','BENIGN_ROUTINE']
    id: int|None=None
    timestamp_iso: str=Field('',max_length=64)
    src_ip: str=Field('',max_length=64)
    dst_ip: str=Field('',max_length=64)
    src_port: str=Field('',max_length=16)
    dst_port: str=Field('',max_length=16)
    service_name: str=Field('',max_length=256)
    alert_type: str=Field('',max_length=128)
    port_class: Literal['STANDARD','RPC_HIGH','FLOOD_EPHEMERAL']='STANDARD'
    sensor_source: str=Field('inside',max_length=32)
    session_cooccurred: int=Field(0,ge=0,le=1)
    sensor_corroboration: Literal['SINGLE_SENSOR','DUAL_SENSOR']='SINGLE_SENSOR'
    true_phase_label: int=0
    source_file: str=Field('',max_length=1024)
    run_id: str|None=Field(None,max_length=128)

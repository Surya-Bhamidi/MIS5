"""Constrained selection on outer-validation inputs only; never accepts test data."""
from dataclasses import asdict
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.models.warning_policy import WarningConfig, WarningPolicy
from evaluate_improvements import metrics


def candidates():
    immediate=dict(confirmations=1,clear_confirmations=1,clear_ratio=1.,cooldown_seconds=0.,max_hold_below_seconds=0.)
    rows=[('immediate',WarningConfig(**immediate))]
    for cooldown in (60.,120.,300.):
        rows.append((f'immediate_cooldown_{int(cooldown)}',WarningConfig(**{**immediate,'cooldown_seconds':cooldown})))
    rows.append(('previous_confirmed',WarningConfig()))
    for ratio in (1.25,2.,4.):
        for cooldown in (0.,300.):
            rows.append((f'fast_{ratio:g}_cooldown_{int(cooldown)}',WarningConfig(
                **{**immediate,'confirmations':2,'fast_ratio':ratio,'cooldown_seconds':cooldown})))
    return rows


def trace(times,scores,threshold,config):
    policy=WarningPolicy(config)
    output=[policy.update(float(t),float(p),threshold) for t,p in zip(times,scores)]
    return np.array([r['warning'] for r in output]),np.array([r['notify'] for r in output])


def guardrails(reference,result):
    failures=[]
    for key in ('timely_notification','timely_warning_episode'):
        if result[key]<reference[key]:failures.append(key)
    for key in ('notification_lead_minutes','episode_lead_minutes'):
        if reference[key] is not None and (result[key] is None or result[key]+1e-9<reference[key]):failures.append(key)
    for key in ('false_notifications','false_warning_episodes','negative_warning_minutes','notifications'):
        if result[key]>reference[key]:failures.append(key)
    return failures


def choose_policy(times,scores,onset,horizon,threshold):
    mask=times<onset;times=times[mask];scores=scores[mask]
    tested=[]
    for name,config in candidates():
        warning,notifications=trace(times,scores,threshold,config)
        result=metrics(times,onset,horizon,warning,notifications)
        tested.append(dict(name=name,config=asdict(config),metrics=result))
    baseline=tested[0]['metrics']
    for candidate in tested:
        candidate['guardrail_failures']=guardrails(baseline,candidate['metrics'])
    if not baseline['timely_notification']:
        chosen=tested[0];reason='No timely validation warning; preserve original responsiveness'
    else:
        eligible=[r for r in tested if not r['guardrail_failures']]
        chosen=min(eligible,key=lambda r:tuple(r['metrics'][k] for k in
            ('false_notifications','false_warning_episodes','negative_warning_minutes','notifications')))
        reason='Best alarm burden among policies preserving all validation guardrails'
    return dict(name=chosen['name'],config=chosen['config'],validation_metrics=chosen['metrics'],
                validation_baseline=baseline,candidates=tested,reason=reason)

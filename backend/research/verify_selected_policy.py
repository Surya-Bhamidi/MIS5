"""Independent candidate/guardrail reconstruction; retain every test regression."""
from pathlib import Path
import hashlib
import json

import numpy as np
import extended_study as study
from audit_operational_improvements import reference_policy,reference_metrics

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'


def violations(base,score):
    failures=[]
    for key in ('timely_notification','timely_warning_episode'):
        if score[key]<base[key]:failures.append(key)
    for key in ('notification_lead_minutes','episode_lead_minutes'):
        if base[key] is not None and (score[key] is None or score[key]+1e-9<base[key]):failures.append(key)
    for key in ('false_notifications','false_warning_episodes','negative_warning_minutes','notifications'):
        if score[key]>base[key]:failures.append(key)
    return failures


def run():
    choices=json.loads((OUT/'policy_selection.json').read_text())
    evaluation=json.loads((OUT/'selected_evaluation.json').read_text())
    previous=json.loads((OUT/'evaluation.json').read_text())
    roots={r['scenario']:r['successful_root'] for r in json.loads((ROOT/'experiments/publication_validation/endpoint_evidence.json').read_text())}
    episodes=study.load('ait');checked=0
    for selection in choices:
        test,val,key,horizon=selection['test'],selection['validation'],selection['available'],selection['horizon']
        with np.load(ROOT/'experiments/current_version/predictions'/f'ait_{test}_{key}_pooled_fixed_blend.npz') as data:
            j=data['horizons'].tolist().index(horizon)
            mask=episodes[val]['times']<roots[val]
            times=episodes[val]['times'][mask];scores=data['validation_risk'][mask,j]
            # Independently reconstruct the full validation candidate table.
            reconstructed=[]
            for candidate in selection['candidates']:
                flags,notices=reference_policy(times,scores,selection['threshold'],candidate['config'])
                result=reference_metrics(times,roots[val],horizon,flags,notices)
                assert result==candidate['metrics']
                reconstructed.append(result)
            baseline=reconstructed[0]
            eligible=[]
            for index,(candidate,score) in enumerate(zip(selection['candidates'],reconstructed)):
                failures=violations(baseline,score)
                assert failures==candidate['guardrail_failures']
                if not failures:eligible.append(index)
            if not baseline['timely_notification']:winner=0
            else:winner=min(eligible,key=lambda index:tuple(reconstructed[index][metric] for metric in
                ('false_notifications','false_warning_episodes','negative_warning_minutes','notifications')))
            chosen=selection['candidates'][winner]
            assert selection['name']==chosen['name'] and selection['config']==chosen['config']
            assert selection['selection_uses_outer_test'] is False
            # Only after the choice is reproduced do test scores enter this check.
            test_mask=data['times']<roots[test]
            test_times=data['times'][test_mask];test_scores=data['risk'][test_mask,j]
        row=next(r for r in evaluation['campaigns'] if (r['campaign'],r['available'],r['horizon'])==(test,key,horizon))
        original=next(r for r in previous['campaigns'] if (r['campaign'],r['available'],r['horizon'])==(test,key,horizon))
        flags,notices=reference_policy(test_times,test_scores,selection['threshold'],chosen['config'])
        expected=reference_metrics(test_times,roots[test],horizon,flags,notices)
        assert row['selected']==expected
        assert row['baseline']==original['baseline'] and row['previous']==original['improved']
        assert row['test_guardrail_regressions']==violations(row['baseline'],expected)
        checked+=1
    for entry in evaluation['summary']:
        group=[r for r in evaluation['campaigns'] if (r['available'],r['horizon'])==(entry['available'],entry['horizon'])]
        assert len(group)==entry['campaigns']==8
        for mode in ('baseline','previous','selected'):
            for metric,value in entry[mode].items():
                if metric=='mean_notification_lead_minutes':
                    leads=[r[mode]['notification_lead_minutes'] for r in group if r[mode]['notification_lead_minutes'] is not None]
                    expected=float(np.mean(leads)) if leads else None
                else:expected=sum(r[mode][metric] for r in group)
                assert value==expected
    for path,digest in json.loads((OUT/'selection_inputs.json').read_text()).items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    regressions=[{k:r[k] for k in ('campaign','available','horizon','test_guardrail_regressions')} for r in evaluation['campaigns'] if r['test_guardrail_regressions']]
    report=dict(passed=True,cases=checked,candidate_tables_reconstructed=True,selection_matches_validation_only_ranking=True,
                test_regressions=regressions,selection_promoted=False,
                reason='Candidate does not preserve every evaluated constraint; retain immediate default and optional confirmed profile')
    (OUT/'selection_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    if not __debug__:raise RuntimeError('Run verification without Python optimization')
    run()

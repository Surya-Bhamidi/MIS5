"""Verify the frozen preset, including one refitted archived campaign forecast."""
import hashlib
import io
import json
import unittest
from datetime import datetime, timezone

import numpy as np
from threadpoolctl import threadpool_limits

import evidence_pilot as pilot
import extended_study as study
import robust_forecasting as robust
import selective_fusion as selective
from freeze_current_version import MODE, OUT, SOURCE


def run():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(pilot.ROOT / 'backend/tests'))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert result.wasSuccessful(), stream.getvalue()
    config = json.loads((OUT / 'config.json').read_text())
    assert config['forecast_mode'] == MODE and config['state_branch_weight'] == .25
    assert config['primary_horizon_minutes'] == 30
    assert config['horizons_minutes'] == study.HORIZONS
    metadata = json.loads((OUT / 'metadata.json').read_text())
    assert len(metadata) == 56
    for row in metadata:
        assert row['weights'] == [.25] * 6 and set(row['calibrators']) == {MODE}
        assert not set(row['train']) & {row['test'], row['validation']}
    thresholds = json.loads((OUT / 'thresholds.json').read_text())
    expected = [r for r in json.loads((SOURCE / 'thresholds.json').read_text()) if r['mode'] == MODE]
    assert thresholds == expected and len(thresholds) == 1344
    summary = json.loads((OUT / 'summary.json').read_text())
    assert summary == [r for r in json.loads((SOURCE / 'summary.json').read_text()) if r['mode'] == MODE]
    paths = sorted((OUT / 'predictions').glob('*.npz'))
    assert len(paths) == 59
    assert {p.name for p in paths} == {p.name for p in (SOURCE / 'predictions').glob(f'*_{MODE}.npz')}
    for path in paths:
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(
            (SOURCE / 'predictions' / path.name).read_bytes()).digest()
    pilot.HORIZONS = study.HORIZONS
    episodes = study.load('ait')
    row = next(m for m in metadata if m['test'] == 'fox' and m['available'] == 'aminer+suricata+wazuh')
    available = row['available'].split('+')
    _, bundle, _ = robust.fit_predict(episodes, row['train'], [row['test']], available)
    episode = episodes[row['test']]
    current = selective.predict_current(bundle, episode, available, row['calibrators'])
    with np.load(OUT / 'predictions' / f'ait_{row["test"]}_{row["available"]}_{MODE}.npz') as saved:
        error = float(np.max(np.abs(current['risk'] - saved['risk'])))
    assert error < 1e-10, error
    prefix = {**episode, 'counts': episode['counts'][:23], 'times': episode['times'][:23],
              'truth': np.full(23, 999), 'onset': -1.}
    limited = selective.predict_current(bundle, prefix, available, row['calibrators'])
    prefix_error = float(np.max(np.abs(current['risk'][:23] - limited['risk'])))
    assert prefix_error < 1e-10, prefix_error
    absent = selective.predict_current(bundle, episode, [], row['calibrators'])
    assert absent['risk'] is None and absent['recommended_action'] is None
    verification = {
        'passed': True, 'regression_tests': result.testsRun, 'regression_output': stream.getvalue(),
        'copied_prediction_archives': len(paths), 'fixed_validation_thresholds': len(thresholds),
        'refitted_campaign': row['test'], 'available': row['available'],
        'refit_archive_max_absolute_error': error, 'prefix_max_absolute_error': prefix_error,
        'no_sensor_abstention': True,
        'scope': 'Packaging and API verification; no new development experiment or independent campaign',
        'utc': datetime.now(timezone.utc).isoformat(),
    }
    (OUT / 'verification.json').write_text(json.dumps(verification, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in verification.items() if k != 'regression_output'}, indent=2), flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=2):
        run()

"""Export presentation plots from frozen results; no model fitting or tuning."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Plots' / 'Results'
FULL = 'aminer+suricata+wazuh'
CURRENT = 'pooled_fixed_blend'
MODELS = ['temporal_boosting', 'conditional_fusion', 'pooled_counts', CURRENT]
LABELS = {
    'temporal_boosting': 'Original\ncounts-only',
    'conditional_fusion': 'Original\nduration/tree fusion',
    'pooled_counts': 'Matched pooled\ncounts-only',
    CURRENT: 'Current fixed\n25% state blend',
}
COLORS = dict(zip(MODELS, ['#4379aa', '#8064a2', '#87939e', '#159b87']))
CAMPAIGNS = ['fox', 'harrison', 'russellmitchell', 'santos', 'shaw', 'wardbeck', 'wheeler', 'wilson']
INPUTS = [
    'experiments/current_version/summary.json',
    'experiments/current_version/config.json',
    'experiments/current_version/verification.json',
    'experiments/selective_fusion/summary.json',
    'experiments/selective_fusion/scored.json',
    'experiments/selective_fusion/cam_transfer.json',
    'experiments/published_comparison/budget_summary.json',
    'experiments/published_comparison/budget_fold_results.json',
]


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_table(name, rows):
    assert rows
    (OUT / f'{name}.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    with (OUT / f'{name}.csv').open('w', newline='', encoding='utf-8') as stream:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def find(rows, **filters):
    found = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
    assert len(found) == 1, (filters, len(found))
    return found[0]


def finish(fig, name, note):
    fig.text(.5, .025, note, ha='center', va='bottom', fontsize=9, color='#475569')
    fig.tight_layout(rect=(0, .09, 1, .93))
    fig.savefig(OUT / f'{name}.png', dpi=300, facecolor='white')
    fig.savefig(OUT / f'{name}.pdf', facecolor='white')
    plt.close(fig)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    before = {p: digest(ROOT / p) for p in INPUTS}
    current = read(INPUTS[0]); config = read(INPUTS[1]); verification = read(INPUTS[2])
    new = read(INPUTS[3]); new_cases = read(INPUTS[4]); cam = read(INPUTS[5])
    old = read(INPUTS[6]); old_cases = read(INPUTS[7])
    assert config['forecast_mode'] == CURRENT and config['state_branch_weight'] == .25
    assert config['primary_horizon_minutes'] == 30 and verification['passed']

    def summary(mode, horizon, available=FULL):
        filters = dict(mode=mode, horizon=horizon, endpoint='successful_root', budget=1)
        if mode in MODELS[:2]:
            assert available == FULL
            row = find(old, **filters)
        else:
            filters.update(available=available, delay_minutes=0)
            row = find(current if mode == CURRENT else new, **filters)
        assert row['campaigns'] == 8
        return dict(available=available, delay_minutes=0) | row

    def cases(mode, horizon, available=FULL):
        rows = old_cases if mode in MODELS[:2] else new_cases
        filters = dict(mode=mode, horizon=horizon, endpoint='successful_root', budget=1)
        if mode not in MODELS[:2]:
            filters.update(available=available, delay_minutes=0)
        return [dict(available=available, delay_minutes=0) | find(rows, scenario=n, **filters)
                for n in CAMPAIGNS]

    exports = []
    for horizon in [15, 30]:
        for mode in MODELS:
            row = summary(mode, horizon)
            group = cases(mode, horizon)
            assert sum(r['strict_warning_recall'] for r in group) == row['strict_warned']
            assert sum(r['false_warning_episodes'] for r in group) == row['false_episodes']
            np.testing.assert_allclose(np.mean([r['brier'] for r in group]), row['mean_brier'], rtol=0, atol=1e-12)
            np.testing.assert_allclose(np.mean([r['average_precision'] for r in group]), row['mean_ap'], rtol=0, atol=1e-12)
            exports.append(dict(model=LABELS[mode].replace('\n', ' '), **row))
    write_table('full_input_comparison_15_30_minutes', exports)

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'pdf.fonttype': 42})
    policy = 'Verified successful-root endpoint | 8 AIT campaigns | Full sensor inputs | No added processing delay\nValidation budget: 1 false episode / 24 negative hours and at most 5 negative warning minutes'
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    fig.suptitle('30-minute early warning: current preset and reference models', fontsize=17, fontweight='bold')
    metrics = [('strict_warned', 'Timely new warnings (higher is better)', 1, lambda v: f'{int(v)}/8'),
               ('false_episodes', 'False alarm episodes (lower is better)', 1, lambda v: str(int(v))),
               ('mean_brier', 'Brier score x 1,000 (lower is better)', 1000, lambda v: f'{v:.4f}'),
               ('mean_ap', 'Average precision (higher is better)', 1, lambda v: f'{v:.4f}')]
    for ax, (key, title, scale, display) in zip(axes.flat, metrics):
        values = [summary(m, 30)[key] * scale for m in MODELS]
        bars = ax.bar(range(len(MODELS)), values, color=[COLORS[m] for m in MODELS], width=.65)
        ax.set_title(title, fontsize=12)
        ax.set_xticks(range(len(MODELS)), [LABELS[m] for m in MODELS], fontsize=9)
        ax.set_axisbelow(True); ax.grid(axis='y', alpha=.2)
        ax.set_ylim(0, 8.8 if key == 'strict_warned' else 1.05 if key == 'mean_ap' else max(values) * 1.25)
        if key == 'strict_warned': ax.set_yticks(range(0, 9, 2))
        for bar, value in zip(bars, values):
            ax.annotate(display(value), (bar.get_x() + bar.get_width() / 2, value),
                        xytext=(0, 5), textcoords='offset points', ha='center', fontweight='bold', fontsize=11)
    finish(fig, '01_30_minute_comparison', policy)

    horizons = config['horizons_minutes']
    horizon_rows = [dict(model=LABELS[m].replace('\n', ' '), **summary(m, h))
                    for h in horizons for m in ['pooled_counts', CURRENT]]
    write_table('matched_baseline_all_horizons', horizon_rows)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    fig.suptitle('Where the state blend helps and where it loses', fontsize=17, fontweight='bold')
    for ax, (key, title, scale) in zip(axes.flat, [
        ('mean_brier', 'Brier score x 1,000 (lower is better)', 1000),
        ('mean_ap', 'Average precision (higher is better)', 1),
        ('strict_warned', 'Timely new warnings (higher is better)', 1),
        ('false_episodes', 'False alarm episodes (lower is better)', 1)]):
        for mode in ['pooled_counts', CURRENT]:
            values = [summary(mode, h)[key] * scale for h in horizons]
            ax.plot(range(len(horizons)), values, marker='o', linewidth=2.2, color=COLORS[mode],
                    label=LABELS[mode].replace('\n', ' '))
        ax.set_xticks(range(len(horizons)), horizons)
        ax.set_xlabel('Forecast horizon (minutes)'); ax.set_title(title, fontsize=12)
        ax.grid(alpha=.2); ax.set_ylim(bottom=0)
        if key == 'strict_warned': ax.set_ylim(0, 8.4); ax.set_yticks(range(0, 9, 2))
        if key == 'mean_ap': ax.set_ylim(0, 1)
        ax.legend(fontsize=9)
    finish(fig, '02_horizon_tradeoffs', policy + '\nBoth models use the same pooled-calibration procedure; separate validation thresholds apply at each horizon.')

    case_rows = [dict(model=LABELS[m].replace('\n', ' '), **r)
                 for m in MODELS for r in cases(m, 30)]
    write_table('campaign_results_30_minutes', case_rows)
    lead = np.array([[r['strict_lead_minutes'] if r['strict_warning_recall'] else np.nan
                      for r in cases(m, 30)] for m in MODELS]).T
    cmap = plt.get_cmap('YlGnBu').copy(); cmap.set_bad('#e7ebef')
    fig, ax = plt.subplots(figsize=(11, 8.5))
    fig.suptitle('30-minute warning lead time by campaign', fontsize=17, fontweight='bold')
    shown = ax.imshow(np.ma.masked_invalid(lead), cmap=cmap, vmin=0, vmax=30, aspect='auto')
    ax.set_xticks(range(len(MODELS)), [LABELS[m] for m in MODELS])
    ax.set_yticks(range(len(CAMPAIGNS)), CAMPAIGNS)
    for i in range(len(CAMPAIGNS)):
        for j in range(len(MODELS)):
            value = lead[i, j]
            ax.text(j, i, 'Missed' if np.isnan(value) else f'{value:.1f} min', ha='center', va='center',
                    color='#334155' if np.isnan(value) or value < 15 else 'white', fontsize=11)
    fig.colorbar(shown, ax=ax, label='Minutes before successful-root outcome')
    finish(fig, '03_campaign_warning_lead_times', policy + '\nA cell counts only a new warning episode starting within the horizon; an earlier persistent alarm is excluded.')

    sensitivity = []
    for label, excluded in [('All 8 campaigns', None), ('Without wheeler (7 campaigns)', 'wheeler')]:
        for mode in MODELS:
            group = [r for r in cases(mode, 30) if r['scenario'] != excluded]
            sensitivity.append(dict(model=LABELS[mode].replace('\n', ' '), mode=mode,
                                    setting=label, campaigns=len(group),
                                    strict_warned=sum(r['strict_warning_recall'] for r in group),
                                    false_episodes=sum(r['false_warning_episodes'] for r in group)))
    write_table('campaign_dependence', sensitivity)
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))
    fig.suptitle('Campaign dependence: the false-alarm gain reverses without wheeler', fontsize=16, fontweight='bold')
    width = .18; x = np.arange(2)
    settings = ['All 8 campaigns', 'Without wheeler (7 campaigns)']
    for ax, metric, title in zip(axes, ['strict_warned', 'false_episodes'],
                                  ['Timely new warnings (higher is better)', 'False alarm episodes (lower is better)']):
        for j, mode in enumerate(MODELS):
            rows = [find(sensitivity, mode=mode, setting=s) for s in settings]
            bars = ax.bar(x + (j - 1.5) * width, [r[metric] for r in rows], width,
                          color=COLORS[mode], label=LABELS[mode].replace('\n', ' '))
            for bar, row in zip(bars, rows):
                text = f'{row[metric]}/{row["campaigns"]}' if metric == 'strict_warned' else str(row[metric])
                ax.annotate(text, (bar.get_x() + width / 2, bar.get_height()), ha='center',
                            xytext=(0, 4), textcoords='offset points', fontsize=10)
        ax.set_xticks(x, ['All 8 campaigns', 'Without wheeler\n7 campaigns'])
        ax.set_title(title, fontsize=12); ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
        ax.set_ylim(0, 8 if metric == 'strict_warned' else 24)
    axes[0].legend(fontsize=9, loc='upper left')
    finish(fig, '04_campaign_dependence', 'Same 30-minute forecasts and frozen validation thresholds; no refitting after removing wheeler.\nThis is a descriptive sensitivity check, not a new independent test.')

    availability = [FULL, 'aminer+suricata', 'aminer+wazuh', 'suricata+wazuh', 'aminer', 'suricata', 'wazuh']
    masks = [dict(model=LABELS[m].replace('\n', ' '), **summary(m, 30, a))
             for a in availability for m in ['pooled_counts', CURRENT]]
    write_table('sensor_availability_30_minutes', masks)
    fig, axes = plt.subplots(1, 2, figsize=(13, 8))
    fig.suptitle('30-minute warning tradeoffs under declared sensor availability', fontsize=16, fontweight='bold')
    y = np.arange(len(availability)); height = .32
    for ax, metric, title in zip(axes, ['strict_warned', 'false_episodes'],
                                  ['Timely new warnings (higher is better)', 'False alarm episodes (lower is better)']):
        for j, mode in enumerate(['pooled_counts', CURRENT]):
            values = [summary(mode, 30, a)[metric] for a in availability]
            bars = ax.barh(y + (j - .5) * height, values, height, color=COLORS[mode],
                           label=LABELS[mode].replace('\n', ' '))
            for bar, value in zip(bars, values):
                ax.annotate(f'{value}/8' if metric == 'strict_warned' else str(value),
                            (value, bar.get_y() + height / 2), xytext=(4, 0),
                            textcoords='offset points', ha='left', va='center', fontsize=10)
        ax.set_yticks(y, [a.replace('+', ' + ') for a in availability], fontsize=9)
        ax.invert_yaxis(); ax.set_title(title, fontsize=12); ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
        ax.set_xlim(0, 9 if metric == 'strict_warned' else max(r[metric] for r in masks) * 1.2 + 1)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='upper center', bbox_to_anchor=(.5, .93), ncol=2, fontsize=10)
    finish(fig, '05_sensor_availability', 'Verified successful-root endpoint | 8 AIT campaigns | 30-minute horizon | No added processing delay\nExperts match each declared availability set; the current blend stays fixed at 25% state-branch weight.')

    external = [r for r in cam if r['mode'] == CURRENT and r['horizon'] in [15, 30] and r['budget'] == 1]
    assert len(external) == 6 and all(r['strict_warning_recall'] == 0 for r in external)
    write_table('external_cam_results', external)
    for name in ['config.json', 'summary.json', 'verification.json']:
        shutil.copy2(ROOT / 'experiments/current_version' / name, OUT / f'current_preset_{name}')
    fixed = summary(CURRENT, 30); original = summary('temporal_boosting', 30)
    improvement = 100 * (original['mean_brier'] - fixed['mean_brier']) / original['mean_brier']
    (OUT / 'README.md').write_text(
        '# Measured results for presentation\n\n'
        'These charts export frozen experimental results; no new fitting or tuning occurs. '
        'Every chart is available as a 300 dpi PNG and a vector PDF. CSV and JSON tables preserve exact values.\n\n'
        '| Figure | Purpose |\n|---|---|\n'
        '| [01](01_30_minute_comparison.png) | Main 30-minute comparison, including the matched calibration control and original fusion. |\n'
        '| [02](02_horizon_tradeoffs.png) | All-six-horizon comparison with matched pooled counts. |\n'
        '| [03](03_campaign_warning_lead_times.png) | Timely warning lead times and missed campaigns. |\n'
        '| [04](04_campaign_dependence.png) | All campaigns versus removing wheeler, retaining frozen thresholds. |\n'
        '| [05](05_sensor_availability.png) | Current preset versus matched counts under seven sensor-availability settings. |\n\n'
        f'The current preset gives **{fixed["strict_warned"]}/8** timely 30-minute warnings versus '
        f'**{original["strict_warned"]}/8** for original counts; Brier is **{improvement:.2f}% lower**, '
        f'with **{fixed["false_episodes"]} versus {original["false_episodes"]}** false episodes. '
        'Average precision is slightly lower. Matched pooled counts gives 3/8 warnings and one false episode, '
        'so the state blend increases both coverage and alarm burden. Original duration/tree fusion gives '
        '4/8 warnings and four false episodes.\n\n'
        'Limitations retained: the aggregate false-episode improvement reverses without wheeler; '
        '15-minute probability error is worse than original counts; CAM transfer gives 0/3 timely warnings '
        'at both 15 and 30 minutes, with an executed-tactic proxy endpoint and missing AMiner. '
        'Response effects are assumed, not physically measured. The preset is a development choice after '
        'reviewing previously inspected campaigns, not an independent confirmation. '
        'No chart ranks complete published systems.\n\n'
        'The successful-root outcome is a sensitivity rescore: forecasting models were trained for scheduled '
        'escalation. The alarm budget constrains validation; it does not guarantee a test false-alarm rate. '
        'Brier and average precision are unweighted campaign means; warning counts and false episodes are totals.\n\n'
        'Sources: [current preset](../../docs/CURRENT_VERSION.md), '
        '[selective-fusion report](../../experiments/selective_fusion/REPORT.md), '
        '[original comparisons](../../experiments/published_comparison/REPORT.md).\n\n'
        'Rebuild from the project root with `python Plots/create_results_plots.py`.\n', encoding='utf-8')
    assert before == {p: digest(ROOT / p) for p in INPUTS}, 'A frozen input changed during export'
    output_files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'manifest.json')
    manifest = {'utc': datetime.now(timezone.utc).isoformat(),
                'status': 'Export of existing exploratory results; no model development or new experiment',
                'endpoint': 'successful_root', 'validation_budget_per_24h': 1, 'delay_minutes': 0,
                'source_sha256': before,
                'script_sha256': digest(Path(__file__)),
                'output_sha256': {p.name: digest(p) for p in output_files},
                'checks': ['unique selected source rows', 'eight-case warning/false-alarm reconstruction',
                           'Brier/AP reconstruction', 'CAM zero-warning reconstruction', 'unchanged inputs']}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Exported 5 figures (PNG + PDF), 6 CSV/JSON tables, frozen preset files, README and hashes to {OUT}')


if __name__ == '__main__':
    run()

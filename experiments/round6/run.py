"""Paired Q4 experiments; synthetic traces stay in the ignored local archive."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'analysis_b'
BASE = HERE / 'baseline'
ARCHIVE = ROOT / '.local_archive' / 'q4_round6'
FILES = ['model.py', 'optimized.py', 'q3_policy.py', 'q4_policy.py', 'simulator.py', 'config.json']
sys.path.insert(0, str(SOURCE))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def freeze():
    if BASE.exists():
        raise FileExistsError('Baseline already exists; it must not be overwritten')
    BASE.mkdir(parents=True)
    for name in FILES:
        shutil.copyfile(SOURCE / name, BASE / name)
    save(BASE / 'manifest.json', dict(
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        sha256={name: digest(BASE / name) for name in FILES}))


VARIANTS = {
    'baseline': {},
    'selected': {},
    'center_gate': {'q4_help_distance': 'center'},
    'no_wait': {'q4_wait_for_survey': False},
    'no_selective': {'q4_selective_remeasure': False},
    'no_refine': {'q4_refine_max_m': 0},
    'shared': {'q4_shared_scan': True},
    'no_shared': {'q4_shared_scan': False},
    'refine100': {'q4_refine_max_m': 100},
    'refine200': {'q4_refine_max_m': 200},
    'wait1000': {'q4_wait_stale_m': 1000},
    'wait1800': {'q4_wait_stale_m': 1800},
    'p3_original': {'q4_wait_mode': 'stale'},
    'inner_refine200': {'q4_wait_mode': 'inner', 'q4_refine_max_m': 200},
    'inner_refine300': {'q4_wait_mode': 'inner', 'q4_refine_max_m': 300},
    'same_side_wait': {'q4_wait_mode': 'same_side'},
    'all_sides_wait': {'q4_wait_mode': 'all_sides'},
}


def cases(suite):
    if suite == 'dev':
        return [(seed, kind) for kind in ['random', 'boundary', 'radius_min', 'all_directional', 'cluster']
                for seed in range(2026095100, 2026095100 + (60 if kind == 'random' else 30))]
    start, counts = {'smoke': (2026100000, [4, 2, 2, 2, 2]),
                     'holdout': (2026101000, [100, 30, 30, 30, 30]),
                     'sensitivity': (2026103000, [20, 10, 10, 10, 10])}[suite]
    return [(start + index * 200 + n, kind)
            for index, (kind, count) in enumerate(zip(
                ['random', 'boundary', 'radius_min', 'all_directional', 'cluster'], counts))
            for n in range(count)]


def validate(sim, policy, sources, status):
    lookup = {s['channel']: s for s in sources}
    pos = np.zeros(2)
    channel, elapsed, removed = 1, 0., set()
    for action in sim.log:
        point = np.asarray(action['position'])
        ch = action['channel']
        assert 1 <= ch <= 20 and np.all(np.isfinite(point))
        elapsed += float(np.linalg.norm(point - pos)) / sim.cfg['speed_m_s']
        pos = point
        if action['action'] == 'measure':
            elapsed += sim.cfg['measure_s'] + (ch != channel) * sim.cfg['switch_s']
            channel = ch
        else:
            success = action['response']['clear_result'] == 'success'
            elapsed += sim.cfg['clear_success_s'] if success else sim.cfg['clear_failure_s']
            if success:
                assert ch not in removed
                assert np.linalg.norm(point - lookup[ch]['position']) <= sim.cfg['clear_m'] + 1e-8
                removed.add(ch)
        assert abs(elapsed - action['response']['virtual_time_s']) < 1e-6
    assert removed == set(lookup) == policy.cleared == sim.removed
    assert abs(sum(sim.parts.values()) - elapsed) < 1e-6
    assert status['termination'] in ('full_coverage', 'count_upper_bound')
    assert status['visited_survey_points'] == 25 or len(removed) == 16
    for cert in policy.certificates:
        truth = np.asarray(lookup[cert['channel']]['position'])
        assert np.linalg.norm(truth - cert['center']) <= cert['radius_m'] + 1e-6
        poly = np.asarray(cert['vertices'])
        edges = np.roll(poly, -1, axis=0) - poly
        delta = truth - poly
        assert np.all(edges[:, 0] * delta[:, 1] - edges[:, 1] * delta[:, 0] >= -1e-5)


def summarize(rows):
    result = {}
    for kind in sorted({r['kind'] for r in rows}):
        group = [r for r in rows if r['kind'] == kind]
        baseline = {r['seed']: r for r in group if r['variant'] == 'baseline'}
        result[kind] = {}
        for variant in sorted({r['variant'] for r in group}):
            rs = [r for r in group if r['variant'] == variant]
            times = np.array([r['seconds_per_source'] for r in rs])
            entry = dict(cases=len(rs), mean=float(times.mean()), p95=float(np.percentile(times, 95)),
                         maximum=float(times.max()), below500=int(sum(times < 500)),
                         sources=sum(r['sources'] for r in rs), cleared=sum(r['cleared'] for r in rs),
                         failures_per_source=float(np.mean([r['failed_clears']/r['sources'] for r in rs])),
                         runtime_mean_s=float(np.mean([r['runtime_s'] for r in rs])),
                         parts={key: float(np.mean([r['parts'][key]/r['sources'] for r in rs]))
                                for key in rs[0]['parts']})
            if baseline and variant != 'baseline':
                diff = np.array([r['seconds_per_source'] - baseline[r['seed']]['seconds_per_source'] for r in rs])
                rng = np.random.default_rng(2026091106)
                # Bound temporary memory while preserving the seeded sample sequence.
                bootstrap = np.concatenate([rng.choice(diff, (100, len(diff))).mean(axis=1)
                                            for _ in range(100)])
                entry['paired'] = dict(mean_delta=float(diff.mean()),
                    ci95=np.percentile(bootstrap, [2.5, 97.5]).tolist(),
                    faster=int(sum(diff < -1e-7)), slower=int(sum(diff > 1e-7)),
                    worst_delta=float(diff.max()), worst_seed=rs[int(diff.argmax())]['seed'])
            result[kind][variant] = entry
    return result


def restore_summary(label):
    if Path(label).name != label:
        raise ValueError('Label must be a single directory name')
    output=ARCHIVE/label
    metadata=json.loads((output/'metadata.json').read_text(encoding='utf-8'))
    with gzip.open(output/'synthetic_actions.jsonl.gz','rt',encoding='utf-8') as stream:
        rows=[json.loads(line)['row'] for line in stream]
    assert len(rows)==len(metadata['cases'])*len(metadata['variants'])
    assert len({(r['seed'],r['kind'],r['variant']) for r in rows})==len(rows)
    summary=summarize(rows)
    save(output/'results.json',dict(metadata=metadata,rows=rows,summary=summary))
    save(HERE/(label+'_summary.json'),dict(metadata=metadata,summary=summary,
         statistics_script_sha256=digest(Path(__file__))))
    print(label,'statistics restored from',len(rows),'completed and validated runs',flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--summarize', help='Rebuild statistics from complete archived traces without rerunning policies')
    parser.add_argument('--suite', choices=['smoke', 'dev', 'holdout', 'sensitivity'], default='smoke')
    parser.add_argument('--variants', nargs='+', choices=list(VARIANTS), default=['baseline', 'selected'])
    parser.add_argument('--label')
    parser.add_argument('--noise', choices=['spatial', 'constant', 'smooth'], default='spatial')
    parser.add_argument('--amplitude', type=float, default=1.)
    parser.add_argument('--random-orientations', action='store_true')
    args = parser.parse_args()
    if args.summarize:
        restore_summary(args.summarize)
        return
    if args.freeze:
        freeze()
        return
    manifest = json.loads((BASE / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['sha256'].items():
        assert digest(BASE / name) == expected, name
    for name in ['model.py', 'optimized.py', 'q3_policy.py', 'simulator.py']:
        assert digest(SOURCE / name) == manifest['sha256'][name], 'Shared dependency changed: ' + name
    from optimized import OptimizedPolicy
    from simulator import LocalSimulator, generate
    spec = importlib.util.spec_from_file_location('q4_round6_baseline', BASE / 'q4_policy.py')
    baseline_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline_module)
    cfg = json.loads((SOURCE / 'config.json').read_text(encoding='utf-8'))
    baseline_cfg = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
    label = args.label or args.suite
    if Path(label).name != label:
        raise ValueError('Label must be a single directory name')
    output = ARCHIVE / label
    output.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copyfile(SOURCE / name, output / name)
    shutil.copyfile(Path(__file__), output / 'run.py')
    metadata = dict(command=sys.argv, python=sys.version, platform=platform.platform(),
                    numpy=np.__version__, scipy=scipy.__version__, baseline=manifest,
                    cfg=cfg, variants={name: VARIANTS[name] for name in args.variants},
                    cases=cases(args.suite), bootstrap_seed=2026091106,
                    sha256={name: digest(SOURCE / name) for name in FILES})
    save(output / 'metadata.json', metadata)
    rows = []
    with gzip.open(output / 'synthetic_actions.jsonl.gz', 'wt', encoding='utf-8') as stream:
        for index, (seed, kind) in enumerate(cases(args.suite)):
            sources = generate(seed, 4, kind)
            if args.random_orientations and kind == 'all_directional':
                rng = np.random.default_rng(seed + 100000)
                for source in sources:
                    source['orientation_deg'] = float(rng.uniform(0, 360))
            for variant in args.variants:
                params = baseline_cfg if variant == 'baseline' else dict(cfg, **VARIANTS[variant])
                sim = LocalSimulator(sources, params, seed, args.noise, args.amplitude)
                policy = OptimizedPolicy(sim, params, 4)
                if variant == 'baseline':
                    policy.planner = baseline_module.Q4Planner(policy)
                start = time.perf_counter()
                status = policy.run()
                runtime = time.perf_counter() - start
                validate(sim, policy, sources, status)
                row = dict(seed=seed, kind=kind, variant=variant, sources=len(sources),
                           cleared=len(policy.cleared), seconds_per_source=sim.time/len(sources),
                           runtime_s=runtime, parts=sim.parts, status=status,
                           failed_clears=sum(a['action'] == 'clear' and a['response']['clear_result'] != 'success' for a in sim.log),
                           measurements=sum(a['action'] == 'measure' for a in sim.log))
                rows.append(row)
                stream.write(json.dumps(dict(row=row, sources=sources, config=params, actions=sim.log,
                                             certificates=policy.certificates), allow_nan=False) + '\n')
            if (index + 1) % 10 == 0:
                print(label, index + 1, '/', len(cases(args.suite)), flush=True)
    summary = summarize(rows)
    save(output / 'results.json', dict(metadata=metadata, rows=rows, summary=summary))
    save(HERE / (label + '_summary.json'), dict(metadata=metadata, summary=summary))
    for kind, variants in summary.items():
        for variant, entry in variants.items():
            print(kind, variant, 'mean', round(entry['mean'], 2), 'p95', round(entry['p95'], 2),
                  'delta', round(entry.get('paired', {}).get('mean_delta', 0), 2), flush=True)


if __name__ == '__main__':
    main()

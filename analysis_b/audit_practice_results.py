"""Audit saved practice runs without contacting the simulator.

Run from the repository root: python analysis_b/audit_practice_results.py
Private per-run output stays in .local_archive/practice_audit/.
Replay stops at the FIRST different action; it never invents a response at
an unobserved position. Thus this checks behavior, not counterfactual speed.
"""
from __future__ import annotations

import collections
import builtins
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'B题演练程序'
LOGS = PACKAGE / 'practice_logs'
OUT = ROOT / '.local_archive/practice_audit'
SEED = 20260913
REPLICATES = 20000
sys.path.insert(0, str(PACKAGE))
from optimized import OptimizedPolicy
from model import enclosing_circle
import q3_policy


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runs():
    runs, seen = [], set()
    for path in sorted(LOGS.rglob('summary.json')):
        actions = path.with_name('actions.jsonl')
        identity = digest(actions)
        if identity in seen:
            continue
        seen.add(identity)
        runs.append(dict(path=str(path.parent.relative_to(ROOT)),
                         config=read(path.with_name('run_config.json')),
                         summary=read(path), actions_sha256=identity))
    return runs


def is_current(run, current):
    meta = run['config']
    q = meta['question']
    if meta['strategy'] != 'shared':
        return False
    names = ['optimized.py', f'q{q}_policy.py']
    if q == 4:
        names.append('q4_optical.py')
    if any(meta['code_sha256'].get(n) != digest(PACKAGE / n) for n in names):
        return False
    # Source review: the historical model lacks ONLY the new six-station
    # branch and its helper; seven-station Q3 and Q4 paths are unchanged.
    allowed_models = {digest(PACKAGE / 'model.py'),
                      'c3b97b1b163f592ea17cb8c7d0648ad92bb1b3dde614a9347c36bac8ff8b91b6'}
    if meta['code_sha256'].get('model.py') not in allowed_models:
        return False
    relevant = lambda cfg: {k: v for k, v in cfg.items()
                           if not k.startswith('q4_' if q == 3 else 'q3_')
                           and k not in ('seed', 'cases_per_question')}
    return relevant(meta['config']) == relevant(current)


def events(run):
    return [json.loads(s) for s in (ROOT / run['path'] / 'actions.jsonl').read_text(
        encoding='utf-8').splitlines() if s.strip()]


def paired_actions(run):
    pending, pairs = {}, []
    for e in events(run):
        if e['event'] == 'request':
            pending[e['payload']['request_id']] = e
        elif e['event'] == 'response' and e['body'].get('accepted'):
            pairs.append((pending[e['request_id']], e))
    return pairs


def check_accounting(run):
    p, channel, total = np.zeros(2), 1, 0.
    parts = dict(move=0., switch=0., measure=0., optical=0., laser=0.)
    cleared, largest, action_count = set(), 0., 0
    for req, resp in paired_actions(run):
        kind, data, body = req['path'], req['payload'], resp['body']
        if kind not in ('/measure', '/clear'):
            continue
        target = np.array([data['position']['x'], data['position']['y']])
        move = float(np.linalg.norm(target - p) / 5)
        parts['move'] += move
        increment = move
        if kind == '/measure':
            switch = int(channel != data['channel'])
            parts['switch'] += switch
            parts['measure'] += 5
            increment += switch + 5
            channel = data['channel']
        else:
            success = body['clear_result'] == 'success'
            if success:
                assert data['channel'] not in cleared
                cleared.add(data['channel'])
            parts['optical'] += 3
            parts['laser'] += 2 * success
            increment += 3 + 2 * success
        total += increment
        p = target
        action_count += 1
        largest = max(largest, abs(total - body['virtual_time_s']))
    s = run['summary']
    assert largest < .002, (run['path'], largest)
    assert len(cleared) == s['successful_clear_count']
    assert abs(total - s['total_virtual_s']) < .002
    assert all(abs(parts[k] - s['time_components_s'][k]) < 1e-6 for k in parts)
    return dict(max_clock_error_s=largest, action_count=action_count)


class Difference(Exception):
    def __init__(self, detail):
        self.detail = detail


class Replay:
    def __init__(self, run):
        self.actions = [(req, resp) for req, resp in paired_actions(run)
                        if req['path'] in ('/measure', '/clear')]
        self.index = 0
        self.max_position_error = 0.

    def perform(self, path, p, ch):
        if self.index >= len(self.actions):
            raise Difference(dict(index=self.index + 1, reason='extra action'))
        req, resp = self.actions[self.index]
        data = req['payload']
        recorded = [data['position']['x'], data['position']['y']]
        error = float(np.linalg.norm(np.asarray(p) - recorded))
        if req['path'] != path or data['channel'] != ch or error > 1e-5:
            raise Difference(dict(index=self.index + 1, recorded_path=req['path'],
                                  proposed_path=path, recorded_channel=data['channel'],
                                  proposed_channel=int(ch), recorded_position=recorded,
                                  proposed_position=np.asarray(p).tolist(), distance_m=error))
        self.max_position_error = max(self.max_position_error, error)
        self.index += 1
        return resp['body']

    def measure(self, p, ch):
        return self.perform('/measure', p, ch)

    def clear(self, p, ch):
        return self.perform('/clear', p, ch)


def replay(run, refinement=True):
    io = Replay(run)
    cfg = dict(run['config']['config'])
    # This is the only behavior-changing Q3 diff found in the source review.
    cfg['q3_refine_max_m'] = 300 if refinement else 0
    policy = OptimizedPolicy(io, cfg, 3, 'shared')
    original_refine = policy.planner.refine
    activations = []
    tie_choices = []
    def replay_min(iterable, *args, **kwargs):
        values = list(iterable)
        chosen = builtins.min(values, *args, **kwargs)
        key = kwargs.get('key')
        if key is None or io.index >= len(io.actions):
            return chosen
        request = io.actions[io.index][0]['payload']
        recorded = np.array([request['position']['x'], request['position']['y']])
        if getattr(key, '__name__', '') == 'cost' and request['channel'] in values:
            value = request['channel']
            if abs(key(value)-key(chosen)) <= 1e-9:
                if value != chosen:
                    tie_choices.append(dict(next_action=io.index+1,
                                            cost_difference_m=float(key(value)-key(chosen))))
                return value
        # Symmetric second points can have costs differing only by machine
        # rounding on different NumPy/BLAS builds. Follow the logged point
        # only within 1e-9 metres of the computed minimum; never override a
        # genuinely different decision or supply an unobserved response.
        for value in values:
            if isinstance(value, np.ndarray) and value.shape == (2,):
                if np.linalg.norm(value-recorded) < 1e-5 and abs(key(value)-key(chosen)) <= 1e-9:
                    if np.linalg.norm(value-chosen) > 1e-5:
                        tie_choices.append(dict(next_action=io.index+1,
                                                cost_difference_m=float(key(value)-key(chosen))))
                    return value
        return chosen

    def counted_refine(ch):
        t = policy.tracks[ch]
        if t['near'] is None:
            _, radius = enclosing_circle(t['poly'])
            if cfg['clear_m'] < radius <= cfg['q3_refine_max_m']:
                activations.append(dict(channel=ch, radius_m=radius,
                                        next_action=io.index + 1))
        return original_refine(ch)

    policy.planner.refine = counted_refine
    q3_policy.min = replay_min
    try:
        result = policy.run()
        assert io.index == len(io.actions), 'Replay did not consume every action'
        assert result['cleared_count'] == run['summary']['successful_clear_count']
        assert result['termination'] == run['summary']['termination']
        return dict(matched=True, actions=io.index, activations=activations, tie_choices=tie_choices,
                    max_position_error_m=io.max_position_error)
    except Difference as exc:
        return dict(matched=False, first_difference=exc.detail, tie_choices=tie_choices,
                    activations=activations)
    finally:
        del q3_policy.min


def stats(runs):
    ss = [r['summary'] for r in runs]
    n = np.array([s['successful_clear_count'] for s in ss])
    t = np.array([s['total_virtual_s'] for s in ss])
    a = t / n
    rng = np.random.default_rng(SEED)
    ci = np.quantile(a[rng.integers(0, len(a), (REPLICATES, len(a)))].mean(axis=1), [.025, .975])
    intercept, slope = np.linalg.lstsq(np.column_stack([np.ones(len(n)), n]), t, rcond=None)[0]
    residual = t - intercept - slope * n
    se = math.sqrt(float(residual @ residual) / (len(n) - 2) / float(((n - n.mean()) ** 2).sum()))
    parts = {k: sum(s['time_components_s'][k] for s in ss) for k in ss[0]['time_components_s']}
    return dict(runs=len(ss), cleared=int(n.sum()), total_s=float(t.sum()),
                case_mean_s=float(a.mean()), pooled_mean_s=float(t.sum() / n.sum()),
                p95_s=float(np.quantile(a, .95)), case_sd_s=float(a.std(ddof=1)),
                total_mean_s=float(t.mean()), total_sd_s=float(t.std(ddof=1)),
                case_mean_ci95=ci.tolist(), minimum_s=float(a.min()), maximum_s=float(a.max()),
                mean_count=float(n.mean()), termination=dict(collections.Counter(s['termination'] for s in ss)),
                time_parts_percent={k: 100*v/t.sum() for k,v in parts.items()},
                failed_clear_per_source=(parts['optical']/3-n.sum())/n.sum(),
                regression=dict(intercept_s=float(intercept), slope_s=float(slope), slope_se_s=se,
                                r_squared=float(1 - residual @ residual / ((t-t.mean())**2).sum())),
                runtime_range_s=[min(s['program_elapsed_s'] for s in ss), max(s['program_elapsed_s'] for s in ss)],
                by_count={str(k):dict(runs=int((n==k).sum()), case_mean_s=float(a[n==k].mean())) for k in sorted(set(n))})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    current = read(PACKAGE / 'config.json')
    runs = load_runs()
    current_runs = {q: [r for r in runs if r['config']['question']==q and is_current(r, current)] for q in (3,4)}
    complete = {q:[r for r in current_runs[q] if r['summary']['status']=='completed'] for q in (3,4)}
    result = dict(seed=SEED, bootstrap_replicates=REPLICATES, percentile_method='numpy linear',
                  code_sha256={n:digest(PACKAGE/n) for n in ('q3_policy.py','optimized.py','model.py','q4_policy.py','q4_optical.py')},
                  stats={f'q{q}':stats(complete[q]) for q in (3,4)},
                  inventory={f'q{q}':dict(all_current=len(current_runs[q]),
                              completed=len(complete[q]), failures=[r['path'] for r in current_runs[q] if r['summary']['status']!='completed']) for q in (3,4)})
    for q in (3,4):
        for r in complete[q]:
            r['accounting'] = check_accounting(r)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    for i,r in enumerate(complete[3]):
        r['current_replay'] = replay(r)
        assert r['current_replay']['matched'], (r['path'], r['current_replay'])
        if (i+1)%8 == 0:
            print(f'Current Q3 replay: {i+1}/{len(complete[3])}', flush=True)
    old = [r for r in runs if r['config']['question']==3
           and 'q3 simulation' in r['path']
           and r['config']['code_sha256'].get('q3_policy.py','').startswith('1d275526')]
    for i,r in enumerate(old):
        r['without_refinement_replay'] = replay(r, refinement=False)
        assert r['without_refinement_replay']['matched'], (r['path'], r['without_refinement_replay'])
        r['current_replay'] = replay(r)
        if (i+1)%5 == 0:
            print(f'Historical Q3 replay: {i+1}/{len(old)}', flush=True)
    result['old_bundle_stats'] = stats(old)
    result['q3_replay'] = dict(current_matched=len(complete[3]), old_without_refinement_matched=len(old),
                              old_current_diverged=sum(not r['current_replay']['matched'] for r in old),
                              current_refinement_activations=sum(len(r['current_replay']['activations']) for r in complete[3]))
    result['runs'] = runs
    (OUT/'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print('Replay summary:', result['q3_replay'], flush=True)
    print('Saved', OUT/'audit.json', flush=True)


if __name__ == '__main__':
    main()

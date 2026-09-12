"""Collect official practice runs of the CURRENT algorithm version into paper-ready tables.

Usage: python analysis_b/collect_official_runs.py [extra_log_dir ...]
Selection rules (no hidden filtering): status=completed, ended_by_exit, and the run
configuration matches the current default behaviour (Q3: 7-station hexagon, mixed
policy, refinement setting equal to config.json; Q4: 22-station list). Excluded runs are listed with the reason.
"""
import glob,json,statistics as st,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DIRS=[ROOT/'B题演练程序/practice_logs',ROOT/'B题演练程序/practice_logs/q3 simulation',ROOT/'B题演练程序/practice_logs/q4 simulation',ROOT/'analysis_b/practice_logs']+[Path(p) for p in sys.argv[1:]]
CFG=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))
Q4_STATIONS=CFG.get('q4_station_list')

def current(question,cfg):
    if question==3:
        if cfg.get('q3_survey_layout')!='hexagon' or cfg.get('q3_policy')!='mixed':return 'Q3 layout/policy differs'
        if cfg.get('q3_ring_radius_m')!=1150 or cfg.get('q3_second_forward_m')!=200 or cfg.get('q3_second_lateral_m')!=100:return 'Q3 parameters differ'
        if cfg.get('q3_refine_max_m',0)!=CFG.get('q3_refine_max_m',0):return 'Q3 refinement setting differs from current config'
        return None
    if cfg.get('q4_policy')!='mixed_ring':return 'Q4 policy differs'
    if cfg.get('q4_station_list')!=Q4_STATIONS:return 'Q4 station layout differs (not the 22-station list)'
    for key in ('q4_selective_remeasure','q4_wait_for_survey','q4_refine_max_m','q4_strip_cover','q4_immediate_near','q4_scan_cost_gate'):
        if cfg.get(key)!=CFG.get(key):return f'Q4 {key} differs'
    return None

rows={3:[],4:[]};excluded=[]
for base in DIRS:
    for d in sorted(glob.glob(str(base/'q*_*'))):
        d=Path(d)
        try:s=json.loads((d/'summary.json').read_text(encoding='utf-8'));rc=json.loads((d/'run_config.json').read_text(encoding='utf-8'))
        except Exception:excluded.append((d.name,'missing summary/run_config'));continue
        q=rc['question']
        if s.get('status')!='completed' or not s.get('ended_by_exit'):excluded.append((d.name,f"status={s.get('status')}"));continue
        reason=current(q,rc['config'])
        if reason:excluded.append((d.name,reason));continue
        n=s['cleared_count'];tc=s['time_components_s']
        rows[q].append(dict(run=d.name,case_code=s.get('case_code',''),sources_cleared=n,total_virtual_s=round(s['total_virtual_s'],3),
            seconds_per_source=round(s['total_virtual_s']/n,2),move_s=round(tc['move'],1),measure_s=tc['measure'],switch_s=tc['switch'],
            optical_s=tc['optical'],laser_s=tc['laser'],actions=s['accepted_actions'],program_s=round(s['program_elapsed_s'],1),
            stations=s.get('visited_survey_points'),q3_policy_sha=rc['code_sha256'].get('q3_policy.py','')[:8],q4_policy_sha=rc['code_sha256'].get('q4_policy.py','')[:8]))

def summarize(rs):
    if not rs:return {}
    per=[r['seconds_per_source'] for r in rs];tot=[r['total_virtual_s'] for r in rs];n=np.array([r['sources_cleared'] for r in rs])
    b,a=np.polyfit(n,tot,1) if len(rs)>2 else (float('nan'),float('nan'))
    by={}
    for k in sorted(set(n)):
        sub=[r['seconds_per_source'] for r in rs if r['sources_cleared']==k];by[int(k)]=dict(runs=len(sub),mean=round(st.mean(sub),1))
    return dict(runs=len(rs),sources=int(n.sum()),mean_s_per_source=round(st.mean(per),2),sd_s_per_source=round(st.stdev(per),2) if len(per)>1 else None,
        median=round(st.median(per),1),p95=round(float(np.percentile(per,95)),1),min=min(per),max=max(per),
        mean_total_s=round(st.mean(tot),1),total_fit=f'total ≈ {a:.0f} + {b:.0f}·n',
        mean_components_per_source={k:round(st.mean(r[k]/r['sources_cleared'] for r in rs),1) for k in ('move_s','measure_s','switch_s','optical_s','laser_s')},
        by_source_count=by)

out=ROOT/'experiments/official_practice'
out.mkdir(exist_ok=True)
result={f'q{q}':dict(summary=summarize(rows[q]),runs=rows[q]) for q in (3,4)}
result['excluded']=excluded
(out/'official_runs.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')
for q in (3,4):
    with (out/f'q{q}_runs.csv').open('w',encoding='utf-8-sig') as f:
        keys=list(rows[q][0].keys()) if rows[q] else [];f.write(','.join(keys)+'\n')
        for r in rows[q]:f.write(','.join(str(r[k]) for k in keys)+'\n')
for q in (3,4):
    s=result[f'q{q}']['summary'];print(f'Q{q}:',json.dumps(s,ensure_ascii=False))
print('excluded:',len(excluded))
for name,reason in excluded:print('  ',name,reason)

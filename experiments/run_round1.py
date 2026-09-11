"""One-factor paired offline experiment. Never connects to a simulator endpoint."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/round1'

def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def write_csv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def specs():
    result=[('development',3,2026090100+i,'random','spatial') for i in range(20)]
    result += [('holdout',3,2026091100+i,'random','spatial') for i in range(100)]
    for j,(kind,noise) in enumerate([('boundary','constant'),('radius_min','spatial'),('cluster','smooth')]):
        result += [('stress',3,2026092100+100*j+i,kind,noise) for i in range(10)]
    result += [('q4_regression',4,2026093100+i,'boundary' if i<5 else 'all_directional','constant') for i in range(10)]
    return result

def validate(sim,policy,sources,cfg):
    import numpy as np
    pos=np.zeros(2);channel=1;clock=0.;removed=set();lookup={s['channel']:s for s in sources}
    for row in sim.log:
        p=np.array(row['position']);ch=row['channel'];clock+=np.linalg.norm(p-pos)/5;pos=p
        if row['action']=='measure':
            clock+=5+(ch!=channel);channel=ch
        else:
            success=row['response']['clear_result']=='success';clock+=5 if success else 3
            if success:
                assert ch not in removed
                assert np.linalg.norm(p-lookup[ch]['position'])<=20+1e-8
                removed.add(ch)
        assert abs(clock-row['response']['virtual_time_s'])<1e-6
    for cert in policy.certificates:
        g=np.array(lookup[cert['channel']]['position']);v=np.array(cert['vertices'])
        assert np.linalg.norm(g-cert['center'])<=cert['radius_m']+1e-6
        assert np.max(np.linalg.norm(v-cert['center'],axis=1))<=cert['radius_m']+1e-6
        for a,b in zip(v,np.roll(v,-1,axis=0)):
            assert (b[0]-a[0])*(g[1]-a[1])-(b[1]-a[1])*(g[0]-a[0])>=-1e-5
    assert len(removed)==len(sources)==len(policy.cleared)
    assert abs(sum(sim.parts.values())-clock)<1e-6
    assert clock<cfg['virtual_limit_s']

def run(version):
    base=OUT/'baseline' if version=='baseline' else ROOT/'analysis_b'
    sys.path.insert(0,str(base))
    import numpy as np
    import scipy
    from optimized import OptimizedPolicy
    from simulator import LocalSimulator,generate
    cfg=json.loads((base/'config.json').read_text(encoding='utf-8'))
    cfg['q3_survey_layout']='grid' if version=='baseline' else 'hexagon'
    meta=dict(version=version,config=cfg,python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),
              code_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in ['model.py','optimized.py','simulator.py','practice_robot.py']},
              runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),specs=specs())
    write_json(OUT/f'{version}_environment.json',meta)
    rows=[]
    with gzip.open(OUT/f'{version}_logs.jsonl.gz','wt',encoding='utf-8') as log:
        for i,(phase,q,seed,kind,noise) in enumerate(specs()):
            sources=generate(seed,q,kind);sim=LocalSimulator(sources,cfg,seed,noise)
            policy=OptimizedPolicy(sim,cfg,q,'shared');start=time.perf_counter();error='';status={}
            try:
                status=policy.run();validate(sim,policy,sources,cfg)
            except Exception as exc:
                error=f'{type(exc).__name__}: {exc}'
            runtime=time.perf_counter()-start;cleared=len(sim.removed)
            measures=sum(r['action']=='measure' for r in sim.log)
            clears=sum(r['action']=='clear' for r in sim.log)
            row=dict(data_source='local_synthetic',case_id=f'local-{q}-{seed}-{kind}',phase=phase,question=q,seed=seed,kind=kind,noise=noise,
                     true_source_count=len(sources),cleared_count=cleared,clear_ratio=cleared/len(sources),virtual_time=sim.time,
                     average_clear_time=sim.time/cleared if cleared else '',real_program_time=runtime,
                     movement_distance=sim.parts['move']*5,measure_count=measures,channel_switch_count=int(sim.parts['switch']),
                     clear_attempt_count=clears,failed_clear_count=clears-cleared,strategy_version=version+'-shared',
                     parameters=json.dumps({'q3_survey_layout':cfg['q3_survey_layout']},sort_keys=True),
                     visited_survey_points=status.get('visited_survey_points',''),termination=status.get('termination',''),
                     move_s=sim.parts['move'],measure_s=sim.parts['measure'],switch_s=sim.parts['switch'],
                     optical_s=sim.parts['optical'],laser_s=sim.parts['laser'],validation_passed=not error,notes=error)
            rows.append(row)
            log.write(json.dumps(dict(row=row,sources=sources,actions=sim.log,certificates=policy.certificates))+'\n')
            if i%10==0 or error:print(version,i+1,'/',len(specs()),phase,error,flush=True)
    write_csv(OUT/f'{version}.csv',rows)
    print(version,'finished',len(rows),'failures',sum(not r['validation_passed'] for r in rows),flush=True)

def summarize():
    import numpy as np
    rows=[]
    for version in ['baseline','candidate']:
        with (OUT/f'{version}.csv').open(encoding='utf-8-sig') as f:rows+=list(csv.DictReader(f))
    write_csv(ROOT/'experiments/results.csv',rows)
    groups=[];regressions=[];rng=np.random.default_rng(2026091199)
    for phase in ['development','holdout','stress','q4_regression']:
        bs=[r for r in rows if r['phase']==phase and r['strategy_version']=='baseline-shared']
        cs=[r for r in rows if r['phase']==phase and r['strategy_version']=='candidate-shared']
        assert [r['case_id'] for r in bs]==[r['case_id'] for r in cs]
        a=np.array([float(r['average_clear_time']) for r in bs]);b=np.array([float(r['average_clear_time']) for r in cs]);delta=a-b
        item=dict(phase=phase,cases=len(bs),baseline_mean=float(a.mean()),candidate_mean=float(b.mean()),reduction=float(1-b.mean()/a.mean()),
                  baseline_p95=float(np.quantile(a,.95)),candidate_p95=float(np.quantile(b,.95)),improved=int(sum(delta>1e-8)),
                  regressed=int(sum(delta< -1e-8)),max_slowdown_s_per_source=float(max(b-a)),
                  ci_saved_s=np.quantile(rng.choice(delta,size=(5000,len(delta)),replace=True).mean(axis=1),[.025,.975]).tolist())
        for label,rr in [('baseline',bs),('candidate',cs)]:
            item[label+'_sources']=sum(int(r['true_source_count']) for r in rr)
            item[label+'_cleared']=sum(int(r['cleared_count']) for r in rr)
            item[label+'_failures']=sum(r['validation_passed']!='True' for r in rr)
            for key in ['virtual_time','movement_distance','measure_count','channel_switch_count','clear_attempt_count','failed_clear_count','real_program_time','visited_survey_points']:
                item[label+'_mean_'+key]=float(np.mean([float(r[key]) for r in rr]))
            item[label+'_max_real_program_time']=max(float(r['real_program_time']) for r in rr)
        for ar,br in zip(bs,cs):
            if float(br['average_clear_time'])>float(ar['average_clear_time'])+1e-8:
                regressions.append(dict(case_id=ar['case_id'],phase=phase,baseline_s_per_source=ar['average_clear_time'],candidate_s_per_source=br['average_clear_time'],
                                        extra_s_per_source=float(br['average_clear_time'])-float(ar['average_clear_time'])))
        groups.append(item)
    write_json(OUT/'summary.json',groups)
    if regressions:write_csv(OUT/'regressions.csv',regressions)
    # Q4 must match every action, rather than merely matching total clearance.
    def action_hashes(version):
        with gzip.open(OUT/f'{version}_logs.jsonl.gz','rt',encoding='utf-8') as f:
            return {r['row']['case_id']:hashlib.sha256(json.dumps(r['actions'],sort_keys=True).encode()).hexdigest()
                    for r in map(json.loads,f) if r['row']['question']==4}
    assert action_hashes('baseline')==action_hashes('candidate')
    print(json.dumps(groups,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['baseline','candidate','summarize']);args=parser.parse_args()
    if args.action=='summarize':summarize()
    else:run(args.action)

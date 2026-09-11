"""Frozen Q3 candidate: 100 fresh validation + 70 stress pairs, Q4 regression."""
import csv,gzip,hashlib,importlib.util,json,platform,sys,time
from pathlib import Path
import numpy as np
from model import survey_points
from optimized import OptimizedPolicy
from simulator import LocalSimulator,generate
from experiments import validate
from test_round3 import coverage_validation
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'analysis_b';OUT=ROOT/'experiments/round3'
CFG=json.loads((BASE/'config.json').read_text());OLD=json.loads((OUT/'baseline/config.json').read_text())

def load_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod);return mod
frozen_model=load_file('round3_frozen_model',OUT/'baseline/model.py')
live_model=sys.modules['model'];sys.modules['model']=frozen_model
try:frozen_optimized=load_file('round3_frozen_optimized',OUT/'baseline/optimized.py')
finally:sys.modules['model']=live_model

def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def source_case(seed,q,kind):
    if kind!='adversarial':return generate(seed,q,kind)
    # Includes center, near-coincident sources, ring points and boundary bisectors.
    pts=[np.zeros(2),np.array([.1,.1]),np.array([4.999,0.])]
    pts+=list(np.array(survey_points(3,CFG))[1:5])
    pts+=[1800*np.array([np.cos(a),np.sin(a)]) for a in np.deg2rad([30,90,150,210,270,330])]
    rotation=(seed%10)*.013;c=np.cos(rotation);s=np.sin(rotation);M=np.array([[c,-s],[s,c]])
    return [dict(channel=i+1,position=(M@p).tolist(),radius_m=1000.,orientation_deg=None) for i,p in enumerate(pts)]

def run(seed,q,kind,noise,amplitude,variant):
    cfg=OLD if variant=='baseline' else CFG
    src=source_case(seed,q,kind);sim=LocalSimulator(src,cfg,seed,noise,amplitude)
    cls=frozen_optimized.OptimizedPolicy if variant=='baseline' else OptimizedPolicy
    policy=cls(sim,cfg,q)
    start=time.perf_counter();status=policy.run();runtime=time.perf_counter()-start
    validate(sim,policy,src)
    # Check all remaining track polygons as well as the clear certificates.
    if hasattr(policy,'tracks'):
        from test_round3 import contained
        truth={s['channel']:np.array(s['position']) for s in src}
        for ch,t in policy.tracks.items():
            if t['near'] is not None:continue
            assert contained(t['poly'],truth[ch][None,:],1e-4).all()
    row=dict(seed=seed,question=q,kind=kind,noise=noise,amplitude=amplitude,variant=variant,
             sources=len(src),cleared=len(sim.removed),average_s=sim.time/len(src),virtual_s=sim.time,
             runtime_s=runtime,measurements=sum(a['action']=='measure' for a in sim.log),
             clear_attempts=sum(a['action']=='clear' for a in sim.log),
             failed_clears=sum(a['action']=='clear' and a['response']['clear_result']!='success' for a in sim.log),
             move_m=sim.parts['move']*cfg['speed_m_s'],actions=len(sim.log),**sim.parts,**status)
    digest=hashlib.sha256(json.dumps(sim.log,sort_keys=True).encode()).hexdigest()
    return row,dict(row=row,sources=src,actions=sim.log,certificates=policy.certificates,actions_sha256=digest)

def summary(rows,group):
    aa=[r for r in rows if r['group']==group and r['variant']=='baseline']
    bb=[r for r in rows if r['group']==group and r['variant']=='candidate']
    a=np.array([r['average_s'] for r in aa]);b=np.array([r['average_s'] for r in bb]);delta=a-b
    ci=np.quantile(np.random.default_rng(311911).choice(delta,(5000,len(delta)),replace=True).mean(axis=1),[.025,.975])
    metrics={}
    for label,rs,ts in [('baseline',aa,a),('candidate',bb,b)]:
        metrics[label]=dict(cases=len(rs),sources=sum(r['sources'] for r in rs),cleared=sum(r['cleared'] for r in rs),
          mean_s=float(ts.mean()),median_s=float(np.median(ts)),p95_s=float(np.quantile(ts,.95)),
          pooled_s=sum(r['virtual_s'] for r in rs)/sum(r['sources'] for r in rs),
          mean_measurements=float(np.mean([r['measurements'] for r in rs])),
          mean_move_m=float(np.mean([r['move_m'] for r in rs])),
          mean_failed_clears=float(np.mean([r['failed_clears'] for r in rs])),
          mean_visited=float(np.mean([r['visited_survey_points'] for r in rs])),
          max_virtual_s=max(r['virtual_s'] for r in rs),max_runtime_s=max(r['runtime_s'] for r in rs),
          cases_below300=int(np.sum(ts<=300)),cases_below225=int(np.sum(ts<=225)))
    return dict(group=group,metrics=metrics,reduction=float(1-b.mean()/a.mean()),
                regressions=int(np.sum(delta< -1e-8)),max_slowdown_s=float(max(0,np.max(-delta))),saved_s_ci95=ci.tolist())

def main():
    if (OUT/'actions.jsonl.gz').exists():raise SystemExit('Refusing to overwrite round3 results')
    dump('coverage.json',coverage_validation())
    specs=[('validation',2031091100+i,3,'random','spatial',1) for i in range(100)]
    for kind,noise,amp in [('boundary','constant',1),('boundary','constant',-1),
                           ('cluster','smooth',1),('radius_min','spatial',1),('random','zero',0),
                           ('adversarial','constant',1),('adversarial','constant',-1)]:
        specs += [('stress',2032091100+i,3,kind,noise,amp) for i in range(10)]
    specs += [('q4_regression',2033091100+i,4,'random','spatial',1) for i in range(20)]
    files=['model.py','optimized.py','q3_policy.py','config.json','simulator.py','experiment3.py','test_round3.py']
    hashes={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in files}
    dump('specification.json',dict(cases=specs,baseline_config=OLD,candidate_config=CFG,code_sha256=hashes,
         note='Candidate and fresh validation seeds fixed before first run; no official connections.'))
    rows=[];identical=0
    with gzip.open(OUT/'actions.jsonl.gz','wt',encoding='utf-8') as log:
        for i,(group,seed,q,kind,noise,amp) in enumerate(specs):
            digests=[]
            for variant in ['baseline','candidate']:
                row,detail=run(seed,q,kind,noise,amp,variant);row['group']=group
                rows.append(row);log.write(json.dumps(detail)+'\n');digests.append(detail['actions_sha256'])
            if q==4:
                assert digests[0]==digests[1],'Q4 behavior changed'
                identical+=1
            if (i+1)%10==0:print(f'Completed {i+1}/{len(specs)} pairs',flush=True)
    with (OUT/'paired.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(results=[summary(rows,g) for g in ['validation','stress','q4_regression']],
                all_cleared=True,q4_identical_action_sequences=identical,official_runs=0)
    dump('summary.json',result)
    dump('regressions.json',[dict(seed=a['seed'],group=a['group'],kind=a['kind'],noise=a['noise'],amplitude=a['amplitude'],
         baseline_s=a['average_s'],candidate_s=b['average_s'],slowdown_s=b['average_s']-a['average_s'])
         for a,b in zip(rows[::2],rows[1::2]) if b['average_s']>a['average_s']+1e-8])
    dump('environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),code_sha256=hashes))
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

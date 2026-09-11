"""Frozen 100 random + 50 stress pairs; only synthetic in-process simulation."""
import csv,gzip,hashlib,importlib.util,json,platform,sys,time
from pathlib import Path
import numpy as np
from model import survey_points
from optimized import OptimizedPolicy
from simulator import LocalSimulator,generate
from experiments import validate
from test_round2 import geometry_validation

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'analysis_b';OUT=ROOT/'experiments/round2'
CFG=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
OLD=json.loads((OUT/'baseline/config.json').read_text(encoding='utf-8'))

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csvsave(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def run(seed,q,kind,noise,variant):
    cfg=OLD if variant=='grid49' else CFG
    sources=generate(seed,q,kind)
    sim=LocalSimulator(sources,cfg,seed,noise)
    policy=OptimizedPolicy(sim,cfg,q)
    started=time.perf_counter();status=policy.run();elapsed=time.perf_counter()-started
    validate(sim,policy,sources)
    row=dict(seed=seed,question=q,kind=kind,noise=noise,variant=variant,sources=len(sources),
             cleared=len(sim.removed),seconds_per_source=sim.time/len(sources),virtual_s=sim.time,
             runtime_s=elapsed,actions=len(sim.log),measurements=sum(a['action']=='measure' for a in sim.log),
             clear_attempts=sum(a['action']=='clear' for a in sim.log),
             move_m=sim.parts['move']*cfg['speed_m_s'],**sim.parts,**status)
    signature=hashlib.sha256(json.dumps(sim.log,sort_keys=True).encode()).hexdigest()
    return row,dict(row=row,sources=sources,actions=sim.log,certificates=policy.certificates,actions_sha256=signature)

def summarize(rows,group):
    pairs={}
    for row in rows:
        if row['group']==group:
            key=(row['seed'],row['kind'],row['noise'])
            pairs.setdefault(key,{})[row['variant']]=row
    aa=[p['grid49'] for p in pairs.values()];bb=[p['triangle27'] for p in pairs.values()]
    a=np.array([r['seconds_per_source'] for r in aa]);b=np.array([r['seconds_per_source'] for r in bb])
    delta=a-b;rng=np.random.default_rng(2026091102)
    ci=np.quantile(rng.choice(delta,size=(5000,len(delta)),replace=True).mean(axis=1),[.025,.975])
    metrics={}
    for name,rs,t in [('grid49',aa,a),('triangle27',bb,b)]:
        metrics[name]=dict(cases=len(rs),sources=sum(r['sources'] for r in rs),cleared=sum(r['cleared'] for r in rs),
            mean_s=float(t.mean()),p95_s=float(np.quantile(t,.95)),
            pooled_s=sum(r['virtual_s'] for r in rs)/sum(r['sources'] for r in rs),
            mean_visited=float(np.mean([r['visited_survey_points'] for r in rs])),
            mean_measurements=float(np.mean([r['measurements'] for r in rs])),
            mean_actions=float(np.mean([r['actions'] for r in rs])),
            mean_move_m=float(np.mean([r['move_m'] for r in rs])),
            mean_clear_attempts=float(np.mean([r['clear_attempts'] for r in rs])))
    return dict(group=group,metrics=metrics,reduction=float(1-b.mean()/a.mean()),
                improved=int(np.sum(delta>1e-8)),regressed=int(np.sum(delta< -1e-8)),
                max_slowdown_s=float(max(0.,np.max(-delta))),saved_s_ci95=ci.tolist())

def main():
    # Refuse to overwrite successful or partial prior runs.
    if (OUT/'paired.csv').exists() or (OUT/'actions.jsonl.gz').exists():
        raise SystemExit('Existing results found; archive deliberately before rerunning.')
    dump(OUT/'geometry.json',geometry_validation())
    specs=[('holdout',20270910+i,4,'random','spatial') for i in range(100)]
    stress=[('boundary','constant'),('cluster','smooth'),('radius_min','spatial'),
            ('all_directional','constant'),('random','smooth')]
    specs += [('stress',20280910+i,4,k,n) for k,n in stress for i in range(10)]
    specs += [('q3_regression',20290910+i,3,'random','spatial') for i in range(10)]
    dump(OUT/'specification.json',dict(cases=specs,baseline_config=OLD,candidate_config=CFG,
         note='Seeds fixed before execution; this is local synthetic evidence, not official tests.'))
    rows=[];q3_equal=0
    with gzip.open(OUT/'actions.jsonl.gz','wt',encoding='utf-8') as log:
        for index,(group,seed,q,kind,noise) in enumerate(specs):
            signatures=[]
            for variant in ['grid49','triangle27']:
                row,detail=run(seed,q,kind,noise,variant);row['group']=group
                rows.append(row);log.write(json.dumps(detail,ensure_ascii=False)+'\n')
                signatures.append(detail['actions_sha256'])
            if q==3:
                assert signatures[0]==signatures[1],'Q3 action sequence changed'
                q3_equal+=1
            if (index+1)%10==0:print(f'Completed pairs {index+1}/{len(specs)}',flush=True)
    csvsave(OUT/'paired.csv',rows)
    regressions=[]
    for a,b in zip(rows[::2],rows[1::2]):
        if b['seconds_per_source']>a['seconds_per_source']+1e-8:
            regressions.append(dict(group=a['group'],seed=a['seed'],kind=a['kind'],noise=a['noise'],
                baseline_s=a['seconds_per_source'],candidate_s=b['seconds_per_source'],
                slowdown_s=b['seconds_per_source']-a['seconds_per_source']))
    dump(OUT/'regressions.json',regressions)
    summary=dict(results=[summarize(rows,g) for g in ['holdout','stress','q3_regression']],
                 q3_identical_action_sequences=q3_equal,all_sources_cleared=True,
                 validation='Every action time, clear distance and localization certificate checked.',
                 official_runs=0)
    dump(OUT/'summary.json',summary)
    paths=[BASE/n for n in ['model.py','optimized.py','config.json','simulator.py','experiment2.py','test_round2.py']]
    dump(OUT/'environment.json',dict(python=sys.version,platform=platform.platform(),numpy=np.__version__,
         code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    for ax,cfg,title in [(axes[0],OLD,'Q4 baseline: 49 stations'),(axes[1],CFG,'Q4 candidate: 27 stations')]:
        pts=np.array(survey_points(4,cfg));ax.scatter(pts[:,0],pts[:,1],s=20)
        ax.add_patch(plt.Circle((0,0),cfg['region_radius_m'],fill=False,color='orange',linewidth=2))
        if cfg.get('q4_survey_layout')=='triangular':
            for i,a in enumerate(pts):
                for b in pts[i+1:]:
                    if abs(np.linalg.norm(a-b)-950)<1e-6:ax.plot([a[0],b[0]],[a[1],b[1]],color='#94a3b8',lw=.6,zorder=0)
        ax.set(aspect='equal',title=title,xlim=(-2700,2700),ylim=(-2700,2700),xlabel='x (m)',ylabel='y (m)')
    fig.tight_layout();fig.savefig(OUT/'stations.png',dpi=160);plt.close(fig)
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()

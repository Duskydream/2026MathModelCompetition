"""Paired ablation on original seeds, then a frozen independent test set."""
import argparse,csv,gzip,hashlib,json,sys,time
from pathlib import Path
import numpy as np
from model import Policy
from optimized import OptimizedPolicy
from simulator import LocalSimulator,generate
from experiments import validate

B=Path(__file__).resolve().parent;OUT=B/'optimization_results';OUT.mkdir(exist_ok=True)
CFG=json.loads((B/'config.json').read_text())

def run(seed,q,variant,kind='random',noise='spatial'):
    sources=generate(seed,q,kind);sim=LocalSimulator(sources,CFG,seed,noise)
    policy=Policy(sim,CFG,q) if variant=='B1' else OptimizedPolicy(sim,CFG,q,variant)
    start=time.perf_counter();status=policy.run();runtime=time.perf_counter()-start;validate(sim,policy,sources)
    row=dict(seed=seed,question=q,variant=variant,kind=kind,noise=noise,sources=len(sources),cleared=len(sim.removed),seconds_per_source=sim.time/len(sources),virtual_s=sim.time,runtime_s=runtime,actions=len(sim.log),move_s=sim.parts['move'],measure_s=sim.parts['measure'],switch_s=sim.parts['switch'],optical_s=sim.parts['optical'],laser_s=sim.parts['laser'],**status)
    return row,dict(row=row,sources=sources,actions=sim.log,certificates=policy.certificates)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['development','holdout','stress'],default='development');args=parser.parse_args()
    phase=args.phase;specs=[]
    if phase=='development':
        specs=[(20260910+i,q,v,'random','spatial') for q in [3,4] for i in range(40) for v in ['B1','route','shared']]
    elif phase=='holdout':
        specs=[(20270910+i,q,v,'random','spatial') for q in [3,4] for i in range(100) for v in ['B1','shared']]
    else:
        specs=[(20280910+i,q,v,k,n) for q in [3,4] for i in range(10) for k,n in [('boundary','constant'),('cluster','smooth'),('radius_min','spatial'),('all_directional','constant'),('random','smooth')] for v in ['B1','shared']]
    rows=[]
    with gzip.open(OUT/f'{phase}_logs.jsonl.gz','wt',encoding='utf-8') as f:
        for idx,spec in enumerate(specs):
            row,detail=run(*spec);rows.append(row);f.write(json.dumps(detail)+'\n')
            if idx%40==0:print(phase,idx+1,'/',len(specs),flush=True)
    # Keep all raw columns even when the baseline lacks optimized counters.
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/f'{phase}.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    result=[];rng=np.random.default_rng(20260910+30000)
    for q in [3,4]:
        base=[r for r in rows if r['question']==q and r['variant']=='B1'];a=np.array([r['seconds_per_source'] for r in base])
        for v in dict.fromkeys(r['variant'] for r in rows):
            rs=[r for r in rows if r['question']==q and r['variant']==v];t=np.array([r['seconds_per_source'] for r in rs]);diff=a-t
            ci=np.quantile(rng.choice(diff,size=(5000,len(diff)),replace=True).mean(axis=1),[.025,.975])
            result.append(dict(question=q,variant=v,cases=len(rs),sources=sum(r['sources'] for r in rs),cleared=sum(r['cleared'] for r in rs),mean_s=float(t.mean()),p95_s=float(np.quantile(t,.95)),reduction=float(1-t.mean()/a.mean()),improved_cases=int(sum(diff>1e-8)),ci_saved_s=ci.tolist(),max_slowdown_per_source=float(max(t-a)),mean_move_per_source=float(np.mean([r['move_s']/r['sources'] for r in rs])),max_runtime_s=max(r['runtime_s'] for r in rs),max_virtual_s=max(r['virtual_s'] for r in rs),max_actions=max(r['actions'] for r in rs)))
    meta=dict(phase=phase,results=result,config=CFG,all_constraint_checks_passed=True,python=sys.version,code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [B/'model.py',B/'simulator.py',B/'optimized.py',Path(__file__)]})
    (OUT/f'{phase}_summary.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

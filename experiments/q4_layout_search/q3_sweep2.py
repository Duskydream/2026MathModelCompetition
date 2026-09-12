import sys,json,statistics as st;sys.path.insert(0,'analysis_b')
import numpy as np
from simulator import LocalSimulator,generate
from optimized import OptimizedPolicy
import optimized
CFG=json.load(open('analysis_b/config.json'))
def ev(over,seeds,patch=None):
    out=[]
    for seed in seeds:
        cfg=dict(CFG,**over);src=generate(seed,3);sim=LocalSimulator(src,cfg,seed,'spatial');pol=OptimizedPolicy(sim,cfg,3)
        if patch:patch(pol)
        pol.run();assert len(pol.cleared)==len(src);out.append(sim.time/len(src))
    return round(st.mean(out),2),round(float(np.percentile(out,95)),1)
seeds=range(2026098000,2026098080)
print('current',ev({},seeds),flush=True)
# shared_scan variants: gap threshold 100 -> 250, range 1300 -> 1000
src=open('analysis_b/optimized.py').read()
def variant(gap,rng,sine):
    code=src.replace("<100:continue",f"<{gap}:continue").replace(">1300:continue",f">{rng}:continue").replace("sine<.12",f"sine<{sine}")
    ns={};exec(compile(code,'opt_variant','exec'),ns);return ns['OptimizedPolicy']
for gap,rng,sine in ((100,1300,.12),(250,1300,.12),(100,1000,.12),(250,1000,.2),(250,1000,.3),(400,1000,.3)):
    cls=variant(gap,rng,sine);out=[]
    for seed in seeds:
        src_=generate(seed,3);sim=LocalSimulator(src_,CFG,seed,'spatial');pol=cls(sim,CFG,3);pol.run();assert len(pol.cleared)==len(src_);out.append(sim.time/len(src_))
    print('shared',gap,rng,sine,round(st.mean(out),2),round(float(np.percentile(out,95)),1),flush=True)

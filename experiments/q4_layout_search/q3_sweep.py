import sys,json,statistics as st;sys.path.insert(0,'analysis_b')
import numpy as np
from simulator import LocalSimulator,generate
from optimized import OptimizedPolicy
CFG=json.load(open('analysis_b/config.json'))
def ev(over,seeds):
    out=[]
    for seed in seeds:
        cfg=dict(CFG,**over);src=generate(seed,3);sim=LocalSimulator(src,cfg,seed,'spatial');pol=OptimizedPolicy(sim,cfg,3);pol.run()
        assert len(pol.cleared)==len(src);out.append(sim.time/len(src))
    return round(st.mean(out),2),round(float(np.percentile(out,95)),1)
seeds=range(2026098000,2026098080)
print('current',ev({},seeds),flush=True)
for ring in (1150,1250,1350,1450):
    print('ring',ring,ev(dict(q3_ring_radius_m=ring),seeds),flush=True)
for f,l in ((150,75),(250,100),(300,100),(300,150),(400,150),(400,200),(500,200)):
    print('second',f,l,ev(dict(q3_second_forward_m=f,q3_second_lateral_m=l),seeds),flush=True)

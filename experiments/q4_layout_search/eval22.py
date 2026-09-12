import sys,json,statistics as st;sys.path.insert(0,'analysis_b')
import numpy as np
from simulator import LocalSimulator,generate
from optimized import OptimizedPolicy
CFG=json.load(open('analysis_b/config.json'))
S=json.load(open(sys.argv[1])) if len(sys.argv)>1 else json.load(open('experiments/q4_layout_search/ring22_stations.json'))
if isinstance(S,dict):S=S['stations']
SETS={'random':[(s,'random') for s in range(2026096000,2026096100)],'boundary':[(s,'boundary') for s in range(2026096100,2026096130)],
      'all_directional':[(s,'all_directional') for s in range(2026096160,2026096190)],'cluster':[(s,'cluster') for s in range(2026096190,2026096220)]}
for label,over in [('ring25',{}),('ring22',dict(q4_station_list=S))]:
    for name,cases in SETS.items():
        out=[];ok=True
        for seed,kind in cases:
            cfg=dict(CFG,**over);src=generate(seed,4,kind);sim=LocalSimulator(src,cfg,seed,'spatial');pol=OptimizedPolicy(sim,cfg,4);pol.run()
            ok&=len(pol.cleared)==len(src);out.append(sim.time/len(src))
        print(label,name,'mean',round(st.mean(out),1),'p95',round(float(np.percentile(out,95)),1),'below500',sum(o<500 for o in out),'all cleared',ok,flush=True)

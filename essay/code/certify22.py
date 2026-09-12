"""Rigorous grid certificate for the 22-station layout (see docs/q4_layout_search.md)."""
import sys,json,math,time;sys.path.insert(0,'experiments/q4_layout_search')
import numpy as np
from layout_opt import slack
S=np.array(json.load(open('experiments/q4_layout_search/ring22_stations.json')));REGION=1800.
h=float(sys.argv[1]) if len(sys.argv)>1 else 1.;delta=h/math.sqrt(2);t=time.time()
xs=np.arange(-REGION-2*h,REGION+3*h,h);worst=math.inf;wpt=None;count=0
for x0 in xs[::200]:
    X,Y=np.meshgrid(xs[(xs>=x0)&(xs<x0+200*h)],xs);G=np.column_stack((X.ravel(),Y.ravel()));G=G[np.hypot(G[:,0],G[:,1])<=REGION+delta]
    if not len(G):continue
    count+=len(G)
    for i in range(0,len(G),80000):
        s=slack(S,G[i:i+80000],delta);k=int(np.argmin(s))
        if s[k]<worst:worst=float(s[k]);wpt=G[i+k]
ok=worst>=delta+1e-6
res=dict(stations=S.tolist(),grid_h=h,delta=delta,grid_points=count,min_slack=worst,worst_point=wpt.tolist(),certified=bool(ok),seconds=time.time()-t)
print(json.dumps({k:v for k,v in res.items() if k!='stations'}))
json.dump(res,open('experiments/q4_layout_search/ring22_certificate.json','w'),indent=1)

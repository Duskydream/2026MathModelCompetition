"""22 站布局的严格网格证书（见 docs/q4_layout_search.md）。

先用 20 m 粗网格快速筛选，再用 h=1 m 细网格做最终认证。判据是最小余量
不小于 δ=h/√2，且全部网格点通过；此时离散网格证书可推广到连续域。网格
按横坐标分块处理，逐块调用 slack 并记录最坏点。
"""
import sys,json,math,time;sys.path.insert(0,'experiments/q4_layout_search')
import numpy as np
from layout_opt import slack
S=np.array(json.load(open('experiments/q4_layout_search/ring22_stations.json')));REGION=1800.
h=float(sys.argv[1]) if len(sys.argv)>1 else 1.;delta=h/math.sqrt(2);t=time.time()
xs=np.arange(-REGION-2*h,REGION+3*h,h);worst=math.inf;wpt=None;count=0
# 每次取 200 列切片，控制单次 slack 的内存。
for x0 in xs[::200]:
    X,Y=np.meshgrid(xs[(xs>=x0)&(xs<x0+200*h)],xs);G=np.column_stack((X.ravel(),Y.ravel()));G=G[np.hypot(G[:,0],G[:,1])<=REGION+delta]
    if not len(G):continue
    count+=len(G)
    for i in range(0,len(G),80000):
        s=slack(S,G[i:i+80000],delta);k=int(np.argmin(s))
        if s[k]<worst:worst=float(s[k]);wpt=G[i+k]
# 全部网格点通过且最小余量不低于 δ，连续域证书成立。
ok=worst>=delta+1e-6
res=dict(stations=S.tolist(),grid_h=h,delta=delta,grid_points=count,min_slack=worst,worst_point=wpt.tolist(),certified=bool(ok),seconds=time.time()-t)
print(json.dumps({k:v for k,v in res.items() if k!='stations'}))
json.dump(res,open('experiments/q4_layout_search/ring22_certificate.json','w'),indent=1)

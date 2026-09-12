"""Polish the 22-station layout so the rigorous certificate (grid h=3, delta=h/sqrt2) holds with margin."""
import sys,json,math,time;sys.path.insert(0,'experiments/q4_layout_search')
import numpy as np
from layout_opt import slack
REGION=1800.;DELTA=3/math.sqrt(2)
def egrid(h):
    xs=np.arange(-REGION-2*h,REGION+3*h,h);X,Y=np.meshgrid(xs,xs);G=np.column_stack((X.ravel(),Y.ravel()))
    return G[np.hypot(G[:,0],G[:,1])<=REGION+DELTA]
def minslack(S,G):
    worst=math.inf
    for i in range(0,len(G),60000):worst=min(worst,float(slack(S,G[i:i+60000],DELTA).min()))
    return worst
S=np.array(json.load(open('experiments/q4_layout_search/ring22_stations.json')))
G6=egrid(6.);rng=np.random.default_rng(int(sys.argv[1]) if len(sys.argv)>1 else 0)
cur=minslack(S,G6);print('start',round(cur,3),flush=True);t0=time.time();budget=float(sys.argv[2]) if len(sys.argv)>2 else 600
while time.time()-t0<budget and cur<6.:
    T=S.copy();k=rng.integers(len(S));T[k]+=rng.normal(0,rng.choice([2.,6.,15.]),2);T=np.round(T,1)
    v=minslack(T,G6)
    if v>cur:S,cur=T,v;print('improved',round(cur,3),'station',k,flush=True)
fine=minslack(S,egrid(3.))
print('final coarse',round(cur,3),'fine(h=3)',round(fine,3),'CERTIFIED' if fine>=DELTA else 'no')
json.dump(dict(stations=S.tolist(),coarse_slack=cur,fine_slack=fine,delta=DELTA,certified=bool(fine>=DELTA)),open(f'experiments/q4_layout_search/polish22_{sys.argv[1] if len(sys.argv)>1 else 0}.json','w'),indent=1)

import sys,math,json,time;sys.path.insert(0,'experiments/q4_layout_search')
import numpy as np
from layout_opt import grid,objective,slack,ring,tour
def core(k,r,ph=math.pi/2):return ring(k,r,ph)
SEEDS={
 'C+8@990+12@1866':[np.zeros(2)]+ring(8,990.)+ring(12,1866.,math.pi/12),
 'C+9@990+12@1866':[np.zeros(2)]+ring(9,990.)+ring(12,1866.,0.),
 'core3@200+6@1050+12@1866':core(3,200.)+ring(6,1050.)+ring(12,1866.,0.),
 'core3@250+6@1080+12@1866':core(3,250.)+ring(6,1080.)+ring(12,1866.,0.),
 'core3@200+7@1050+12@1866':core(3,200.)+ring(7,1050.)+ring(12,1866.,0.),
 'C+7@990+12@1866':[np.zeros(2)]+ring(7,990.)+ring(12,1866.,0.),
 'core2@300+6@1050+12@1866':ring(2,300.,math.pi/2)+ring(6,1050.)+ring(12,1866.,0.),
}
def local(S,G,m,budget,rng):
    S=np.array(S);cur,_=objective(S,G,m);t0=time.time()
    while time.time()-t0<budget:
        T=S.copy();k=rng.integers(len(S));T[k]+=rng.normal(0,rng.choice([5.,15.,40.]),2)
        v,_=objective(T,G,m)
        if v>cur:S,cur=T,v
    return cur,S
if __name__=='__main__':
    names=sys.argv[1].split(',');budget=float(sys.argv[2]);m=float(sys.argv[3]) if len(sys.argv)>3 else 15.
    G=grid(30.);rng=np.random.default_rng(0);out={}
    for name in names:
        S=SEEDS[name];v0,_=objective(S,G,m)
        v,S2=local(S,G,m,budget,rng)
        fine=[(mm,round(objective(S2,grid(10.),mm)[0],1)) for mm in (0.,5.,10.,15.)]
        out[name]=dict(n=len(S2),seed_slack=v0,opt_slack=v,fine=fine,tour=tour(list(S2)),stations=S2.tolist())
        print(name,'n',len(S2),'seed',round(v0,1),'opt',round(v,1),'fine',fine,'tour',round(tour(list(S2))),flush=True)
    json.dump(out,open(f'experiments/q4_layout_search/refine_{names[0].replace("@","_").replace("+","_")}.json','w'),indent=1)

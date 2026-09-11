"""Q3 development only. All decisions use observations; synthetic truth only in validation."""
import json,math,sys,time,csv
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'analysis_b'))
import optimized
from optimized import OptimizedPolicy
from model import direction,enclosing_circle,survey_points
from simulator import LocalSimulator,generate
from experiments import validate
import importlib.util
def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module
_saved_model=sys.modules['model']
sys.modules['model']=_load('development_frozen_model',ROOT/'experiments/round3/baseline/model.py')
try:
    OptimizedPolicy=_load('development_frozen_optimized',ROOT/'experiments/round3/baseline/optimized.py').OptimizedPolicy
finally:sys.modules['model']=_saved_model
CFG=json.loads((ROOT/'experiments/round3/baseline/config.json').read_text())
OUT=ROOT/'experiments/round3'

class Candidate(OptimizedPolicy):
    def __init__(self,io,cfg,q,params):
        super().__init__(io,cfg,q);self.params=params
    def destination(self,ch):
        t=self.tracks[ch]
        if t['near'] is not None:return t['near'],False
        c,rad=enclosing_circle(t['poly'])
        if rad<=20-1e-6 or t['count']>=2:return c,False
        u=direction(t['deg']);v=np.array([-u[1],u[0]])
        f,l=self.params.get('second',(650,250))
        candidates=[t['origin']+f*u+sign*l*v for sign in [-1,1]]
        q=min(candidates,key=lambda x:np.linalg.norm(x-self.pos)+self.params.get('score',0)*np.linalg.norm(x-c))
        return q,True
    def cost(self,ch):
        q,need=self.destination(ch)
        c,_=enclosing_circle(self.tracks[ch]['poly'])
        return np.linalg.norm(q-self.pos)+self.params.get('score',0)*(np.linalg.norm(q-c) if need else 0)
    def run(self):
        rad=self.params.get('ring',1800*math.cos(math.pi/6))
        points=[np.zeros(2)]+[rad*direction(60*k) for k in range(6)]
        visited=0
        while points:
            idx=min(range(len(points)),key=lambda i:np.linalg.norm(points[i]-self.pos))
            p=points.pop(idx);visited+=1;self.tracks={}
            channels=sorted((c for c in range(1,21) if c not in self.cleared),key=lambda c:(c!=self.channel,c))
            for ch in channels:
                r=self.measure(p,ch)
                if r['measure_result']!='no_signal':self.make_track(ch,p,r)
            while any(ch not in self.cleared for ch in self.tracks):
                remaining=[ch for ch in self.tracks if ch not in self.cleared]
                ch=min(remaining,key=self.cost)
                q,need=self.destination(ch)
                if need:
                    r=self.measure(q,ch);self.update(ch,q,r);self.shared_scan(exclude=ch)
                self.finish(ch);self.shared_scan()
            if len(self.cleared)==16:break
        return dict(cleared_count=len(self.cleared),visited_survey_points=visited)


class Coverage:
    """Convex cells partition an OUTER polygon of the target disk."""
    def __init__(self,stations,cfg):
        from model import clip
        radius=cfg['region_radius_m'];n=96
        angles=(np.arange(n)+.5)*2*np.pi/n
        outer=radius/np.cos(np.pi/n)*np.column_stack([np.cos(angles),np.sin(angles)])
        triangles=[];owners=[]
        for owner,station in enumerate(stations):
            others=np.array([p for j,p in enumerate(stations) if j!=owner])
            poly=clip(outer,2*(others-station),np.sum(others*others,axis=1)-station@station)
            assert np.max(np.linalg.norm(poly-station,axis=1))<cfg['receiver_radius_min_m']-1e-6
            center=poly.mean(axis=0)
            def split(t):
                lengths=[np.linalg.norm(t[(i+1)%3]-t[i]) for i in range(3)]
                i=int(np.argmax(lengths))
                if lengths[i]<=150:
                    triangles.append(t);owners.append(owner);return
                a,b,c=t[i],t[(i+1)%3],t[(i+2)%3];mid=(a+b)/2
                split(np.array([a,mid,c]));split(np.array([mid,b,c]))
            for a,b in zip(poly,np.roll(poly,-1,axis=0)):split(np.array([center,a,b]))
        self.triangles=np.array(triangles);self.owners=np.array(owners);self.covered=np.zeros(len(owners),bool)
        t=self.triangles
        u=t[:,1]-t[:,0];v=t[:,2]-t[:,0]
        self.areas=abs(u[:,0]*v[:,1]-u[:,1]*v[:,0])/2
        self.radius=cfg['receiver_radius_min_m']
    def hit(self,p):
        return np.all(np.sum((self.triangles-p)**2,axis=-1)<=(self.radius-1e-6)**2,axis=1)
    def gain(self,p):return float(self.areas[self.hit(p)&~self.covered].sum())
    def record(self,p):self.covered|=self.hit(p)
    def needed(self,i):return bool(np.any(~self.covered[self.owners==i]))

class Opportunistic(Candidate):
    def sweep(self,p):
        for ch in sorted((ch for ch in range(1,21) if ch not in self.cleared and ch not in self.tracks),
                         key=lambda ch:(ch!=self.channel,ch)):
            r=self.measure(p,ch)
            if r['measure_result']!='no_signal':self.make_track(ch,p,r)
        self.coverage.record(p)
    def run(self):
        stations=[np.zeros(2)]+[self.params.get('ring',1150)*direction(60*k) for k in range(6)]
        self.coverage=Coverage(stations,self.cfg);visited=0;extra=0
        while len(self.cleared)<16:
            remaining=[ch for ch in self.tracks if ch not in self.cleared]
            if remaining:
                ch=min(remaining,key=self.cost)
                q,need=self.destination(ch)
                if need:
                    r=self.measure(q,ch);self.update(ch,q,r);self.shared_scan(exclude=ch)
                self.finish(ch);self.shared_scan()
                if self.coverage.gain(self.pos)>self.params.get('gain',500000):
                    self.sweep(self.pos.copy());extra+=1
            else:
                required=[i for i in range(len(stations)) if self.coverage.needed(i)]
                if not required:break
                i=min(required,key=lambda i:np.linalg.norm(stations[i]-self.pos))
                self.sweep(stations[i]);visited+=1
        assert self.coverage.covered.all() or len(self.cleared)==16
        return dict(cleared_count=len(self.cleared),visited_survey_points=visited,extra_sweeps=extra)


class Informed(Candidate):
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw);self.silent={ch:[] for ch in range(1,21)}
    def measure(self,p,ch):
        r=super().measure(p,ch)
        if r['measure_result']=='no_signal':self.silent[ch].append(np.array(p).copy())
        return r
    def shrink(self,ch):
        from model import clip
        from scipy.spatial import ConvexHull
        t=self.tracks[ch];poly=t['poly']
        if not self.params.get('bounds'):return
        n=48;a=np.arange(n)*2*np.pi/n;A=np.column_stack([np.cos(a),np.sin(a)])
        poly=clip(poly,A,np.full(n,self.cfg['region_radius_m']))
        # Hull of edge portions outside a slightly smaller reception disk.
        # This hull contains P minus the open disk, even for disconnected remnants.
        for s in self.silent[ch]:
            points=[];r=self.cfg['receiver_radius_min_m']-1e-5
            for a,b in zip(poly,np.roll(poly,-1,axis=0)):
                delta=a-s;edge=b-a
                if delta@delta>=r*r:points.append(a)
                aa=edge@edge;bb=2*delta@edge;cc=delta@delta-r*r
                disc=bb*bb-4*aa*cc
                if aa>1e-16 and disc>=0:
                    for fraction in [(-bb-np.sqrt(disc))/(2*aa),(-bb+np.sqrt(disc))/(2*aa)]:
                        if 0<=fraction<=1:points.append(a+fraction*edge)
            if len(points)>=3:
                points=np.unique(np.round(points,9),axis=0)
                if len(points)>=3:
                    try:poly=points[ConvexHull(points).vertices]
                    except Exception:pass
        assert len(poly)>0
        t['poly']=poly
    def make_track(self,ch,p,r):
        super().make_track(ch,p,r);self.shrink(ch)
    def update(self,ch,p,r):
        super().update(ch,p,r);self.shrink(ch)
    def run(self):
        points=[np.zeros(2)]+[self.params.get('ring',1150)*direction(60*k) for k in range(6)]
        visited=0
        while points or any(ch not in self.cleared for ch in self.tracks):
            pending=[ch for ch in self.tracks if ch not in self.cleared]
            ch=min(pending,key=self.cost) if pending else None
            i=min(range(len(points)),key=lambda i:np.linalg.norm(points[i]-self.pos)) if points else None
            take_station=i is not None and (ch is None or
                self.params.get('mixed',False) and np.linalg.norm(points[i]-self.pos)*self.params.get('station_weight',1)<self.cost(ch))
            if take_station:
                p=points.pop(i);visited+=1
                channels=sorted((c for c in range(1,21) if c not in self.cleared),key=lambda c:(c!=self.channel,c))
                for c in channels:
                    r=self.measure(p,c)
                    if c in self.tracks:self.update(c,p,r)
                    elif r['measure_result']!='no_signal':self.make_track(c,p,r)
            else:
                q,need=self.destination(ch)
                if need:
                    r=self.measure(q,ch);self.update(ch,q,r);self.shared_scan(exclude=ch)
                self.finish(ch);self.shared_scan()
            if len(self.cleared)==16:break
        return dict(cleared_count=len(self.cleared),visited_survey_points=visited)

def run(params,seeds=range(20260910,20260930)):
    rows=[]
    for seed in seeds:
        src=generate(seed,3);sim=LocalSimulator(src,CFG,seed)
        p=OptimizedPolicy(sim,CFG,3) if params is None else (Informed if params.get('informed') else Opportunistic if params.get('opportunistic') else Candidate)(sim,CFG,3,params)
        status=p.run();validate(sim,p,src)
        rows.append(dict(seed=seed,sources=len(src),cleared=len(sim.removed),average=sim.time/len(src),
                         move=sim.parts['move']/len(src),measurements=sum(a['action']=='measure' for a in sim.log),
                         failed=sum(a['action']=='clear' and a['response']['clear_result']!='success' for a in sim.log)))
    return rows

def main():
    common=dict(ring=1150,informed=True,bounds=True,mixed=True,score=1)
    variants={}
    for second in [(200,100),(300,100),(300,150),(400,150),(500,150)]:
        variants[f'second_{second}']=dict(common,second=second)
    for weight in [.6,1.4]:
        variants[f'station_weight_{weight}']=dict(common,second=(400,150),station_weight=weight)
    variants['score0']=dict(common,second=(400,150),score=0)
    results={}
    for name,params in variants.items():
        rows=run(params);results[name]=dict(params=params,rows=rows)
        print(name,round(np.mean([r['average'] for r in rows]),3),round(np.mean([r['move'] for r in rows]),3),flush=True)
    (OUT/'development/development4_reproduction.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()

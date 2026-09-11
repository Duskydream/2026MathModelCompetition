"""Independent Q4 prototypes; local synthetic data only."""
import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis_b'))
from optimized import OptimizedPolicy
from q3_policy import Q3Planner
from model import clip,survey_points,enclosing_circle,direction
from simulator import LocalSimulator,generate

def ordered(points,start):
    remaining=list(points);route=[np.array(start)]
    while remaining:
        i=min(range(len(remaining)),key=lambda i:np.linalg.norm(remaining[i]-route[-1]))
        route.append(remaining.pop(i))
    for _ in range(30):
        changed=False
        for i in range(1,len(route)-1):
            for j in range(i+1,len(route)):
                before=np.linalg.norm(route[i]-route[i-1])
                after=np.linalg.norm(route[j]-route[i-1])
                if j+1<len(route):
                    before+=np.linalg.norm(route[j+1]-route[j])
                    after+=np.linalg.norm(route[j+1]-route[i])
                if after<before-1e-7:route[i:j+1]=reversed(route[i:j+1]);changed=True
        if not changed:break
    return route[1:]

class Planner(Q3Planner):
    def observe(self,*args):pass
    def constrain(self,ch):
        p=self.p;t=p.tracks[ch]
        if t['near'] is not None:return
        poly=clip(t['poly'],self.region_normals,np.full(48,p.cfg['region_radius_m']+1e-7))
        if not len(poly):raise RuntimeError('empty region')
        t['poly']=poly
    def run(self):
        p=self.p;points=survey_points(4,p.cfg);visited=0
        if p.cfg.get('ring25',False):
            sys.path.insert(0,str(ROOT/'experiments/q4_geometry'))
            from search_rings import ring25_points
            points=ring25_points(p.cfg)
        fixed=p.cfg.get('fixed',False)
        if fixed:points=ordered(points,p.pos)
        while points or any(ch not in p.cleared for ch in p.tracks):
            pending=[ch for ch in p.tracks if ch not in p.cleared]
            index=(0 if fixed else min(range(len(points)),key=lambda i:np.linalg.norm(points[i]-p.pos))) if points else None
            def score(ch):
                cost=self.cost(ch)
                if index is not None and p.cfg.get('detour',False):
                    from model import enclosing_circle
                    center,_=enclosing_circle(p.tracks[ch]['poly'])
                    cost+=np.linalg.norm(center-points[index])-np.linalg.norm(p.pos-points[index])
                return cost
            ch=min(pending,key=score) if pending else None
            threshold=(p.cfg.get('threshold',250) if p.cfg.get('detour',False) else np.linalg.norm(points[index]-p.pos)) if index is not None else 0
            if index is not None and (ch is None or threshold<score(ch)):
                station=points.pop(index);visited+=1
                channels=sorted((c for c in range(1,21) if c not in p.cleared),key=lambda c:(c!=p.channel,c))
                for c in channels:
                    response=p.measure(station,c)
                    if c in p.tracks:p.update(c,station,response)
                    elif response['measure_result']!='no_signal':p.make_track(c,station,response)
            else:
                point,needs_measure=self.destination(ch)
                if needs_measure:
                    response=p.measure(point,ch);p.update(ch,point,response)
                    p.shared_scan(exclude=ch)
                p.finish(ch);p.shared_scan()
            if len(p.cleared)==16:break
        return {'visited_survey_points':visited}

class Candidate(OptimizedPolicy):
    def __init__(self,transport,cfg,question=4,variant='shared'):
        super().__init__(transport,cfg,question,variant)
        self.q3_planner=Planner(self)
    def finish(self,ch):
        t=self.tracks[ch]
        for attempt in range(self.cfg.get('extra_refine',0)):
            c,r=enclosing_circle(t['poly'])
            if t['near'] is not None or r<=20-1e-6:break
            u=direction(t['deg']);v=np.array([-u[1],u[0]])
            if attempt==0 and t['count']==1:
                last=t['sample_points'][-1]
                q=last-2*np.dot(last-t['origin'],v)*v
            else:q=c+((-1)**attempt)*75*v
            response=self.measure(q,ch);self.update(ch,q,response)
        super().finish(ch)

if __name__=='__main__':
    cfg=json.loads((ROOT/'analysis_b/config.json').read_text())
    rows=[]
    n=int(sys.argv[1]) if len(sys.argv)>1 else 8
    variants=[('ring25',200,100),('ring25fixed',200,100),('ring25refine',200,100)]
    for name,f,l in variants:
        for i in range(n):
            seed=2026094400+i;kind='random';sources=generate(seed,4,kind)
            local=dict(cfg,q3_second_forward_m=f,q3_second_lateral_m=l)
            if name.startswith(('fixed','detour')):local['fixed']=True
            if name.startswith('detour'):local.update(detour=True,threshold=int(name[6:]))
            if name.startswith('refine'):local['extra_refine']=int(name[6:])
            if name.startswith('ring25'):local['ring25']=True
            if name=='ring25fixed':local['fixed']=True
            if name=='ring25refine':local['extra_refine']=1
            sim=LocalSimulator(sources,local,seed)
            policy=(OptimizedPolicy if name=='main' else Candidate)(sim,local,4,'shared')
            error=''
            try:policy.run();assert len(sim.removed)==len(sources)
            except Exception as e:error=repr(e)
            rows.append(dict(variant=name,seed=seed,per_source=sim.time/len(sources),cleared=len(sim.removed),n=len(sources),error=error,parts=sim.parts))
        rr=[r for r in rows if r['variant']==name]
        print(name,'mean',np.mean([r['per_source'] for r in rr]),'max',max(r['per_source'] for r in rr),'errors',[r['error'] for r in rr if r['error']],flush=True)
        Path(__file__).with_name('results.json').write_text(json.dumps(rows,indent=2))

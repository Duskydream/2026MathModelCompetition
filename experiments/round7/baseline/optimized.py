"""Route ordering and shared stations; only observed responses enter decisions."""
import numpy as np
from model import Policy,direction,initial_polygon,clip,bearing_halfplanes,enclosing_circle,diameter,optical_cells,survey_points

class OptimizedPolicy(Policy):
    def __init__(self,transport,cfg,question,variant='shared'):
        super().__init__(transport,cfg,question,'triangulate')
        self.variant=variant;self.tracks={};self.shared_attempts=0;self.shared_hits=0
        self.q3_planner=None
        if question==3 and variant=='shared' and cfg.get('q3_policy','legacy')=='mixed':
            from q3_policy import Q3Planner
            self.q3_planner=Q3Planner(self)
        self.planner=self.q3_planner
        if question==4 and variant=='shared' and cfg.get('q4_policy','legacy')=='mixed_ring':
            from q4_policy import Q4Planner
            self.planner=Q4Planner(self)
    def measure(self,p,ch):
        response=super().measure(p,ch)
        if self.planner is not None:self.planner.observe(p,ch,response)
        return response
    def make_track(self,ch,p,r):
        deg=r.get('svd_deg',0.)
        self.tracks[ch]={'origin':p.copy(),'deg':deg,'poly':initial_polygon(p,deg,self.cfg),'count':1,'near':p.copy() if r['measure_result']=='near' else None,'extra':0,'sample_points':[p.copy()]}
        if self.planner is not None:self.planner.constrain(ch)
    def update(self,ch,p,r):
        t=self.tracks[ch];t['sample_points'].append(p.copy())
        if r['measure_result']=='near':t['near']=p.copy();return
        if r['measure_result']=='direction':
            A,b=bearing_halfplanes(p,r['svd_deg'],self.cfg['bearing_bound_deg']);t['poly']=clip(t['poly'],A,b)
            if not len(t['poly']):raise RuntimeError('Inconsistent observed bearings')
            t['count']+=1
        if self.planner is not None:self.planner.constrain(ch)
    def destination(self,ch):
        if self.planner is not None:return self.planner.destination(ch)
        t=self.tracks[ch]
        if t['near'] is not None:return t['near'],False
        c,rad=enclosing_circle(t['poly'])
        if self.variant=='shared' and (rad<=20-1e-6 or t['count']>=2):return c,False
        u=direction(t['deg']);v=np.array([-u[1],u[0]])
        candidates=[t['origin']+650*u+sign*250*v for sign in [-1,1]]
        q=min(candidates,key=lambda x:np.linalg.norm(x-self.pos))
        return q,True
    def shared_scan(self,exclude=None):
        if self.variant!='shared':return
        station=self.pos.copy()
        for ch in sorted(self.tracks):
            if ch in self.cleared or ch==exclude:continue
            t=self.tracks[ch]
            if t['near'] is not None or t['count']>=3 or t['extra']>=4:continue
            if min(np.linalg.norm(station-p) for p in t['sample_points'])<100:continue
            c,rad=enclosing_circle(t['poly'])
            if rad<=20 or np.linalg.norm(c-station)>1300:continue
            a=c-t['origin'];b=c-station
            sine=abs(a[0]*b[1]-a[1]*b[0])/max(np.linalg.norm(a)*np.linalg.norm(b),1e-9)
            if sine<.12:continue
            t['extra']+=1;self.shared_attempts+=1
            r=self.measure(station,ch);self.update(ch,station,r)
            if r['measure_result']!='no_signal':self.shared_hits+=1
            if r['measure_result']=='near':
                if not self.clear(station,ch):raise RuntimeError('near clear failed')
    def finish(self,ch):
        t=self.tracks[ch]
        if t['near'] is not None:
            if not self.clear(t['near'],ch):raise RuntimeError('near clear failed')
            return
        poly=t['poly'];c,rad=enclosing_circle(poly)
        self.certificates.append(dict(channel=ch,center=c.tolist(),radius_m=rad,diameter_m=diameter(poly),vertices=poly.tolist()))
        if rad<=20-1e-6:
            if not self.clear(c,ch):raise RuntimeError('Certified clear failed')
            return
        cells=optical_cells(poly,t['origin'],t['deg'],self.cfg['optical_grid_m'])
        if np.linalg.norm(cells[-1]-self.pos)<np.linalg.norm(cells[0]-self.pos):cells.reverse()
        for p in cells:
            if self.clear(p,ch):return
        raise RuntimeError('Optical cover exhausted')
    def run(self):
        if self.planner is not None:return self.planner.run()
        points=survey_points(self.question,self.cfg);visited=0
        while points:
            idx=min(range(len(points)),key=lambda i:np.linalg.norm(points[i]-self.pos));p=points.pop(idx);visited+=1
            self.tracks={}
            channels=sorted((c for c in range(1,21) if c not in self.cleared),key=lambda c:(c!=self.channel,c))
            for ch in channels:
                r=self.measure(p,ch)
                if r['measure_result']!='no_signal':self.make_track(ch,p,r)
            while any(ch not in self.cleared for ch in self.tracks):
                remaining=[ch for ch in self.tracks if ch not in self.cleared]
                ch=min(remaining,key=lambda ch:np.linalg.norm(self.destination(ch)[0]-self.pos))
                q,needs_measure=self.destination(ch)
                if needs_measure:
                    r=self.measure(q,ch);self.update(ch,q,r)
                    self.shared_scan(exclude=ch)
                self.finish(ch)
                self.shared_scan()
            if len(self.cleared)==16:break
        return dict(cleared_count=len(self.cleared),visited_survey_points=visited,termination='count_upper_bound' if len(self.cleared)==16 else 'full_coverage',shared_attempts=self.shared_attempts,shared_hits=self.shared_hits)

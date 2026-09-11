"""Q4 candidates; use observations only and keep the original discovery certificate."""
import importlib.util
from pathlib import Path
import numpy as np
from model import enclosing_circle,diameter,optical_cells
from q4_optical import clearing_route,route_seconds

SPEC=importlib.util.spec_from_file_location('round7_frozen_planner',Path(__file__).parent/'baseline/q4_policy.py')
BASE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(BASE)


class Candidate(BASE.Q4Planner):
    def __init__(self,policy):
        super().__init__(policy)
        self.original_finish=policy.finish
        policy.finish=self.finish
        self.routes=0;self.saved_bound=0.;self.original_wait=self.wait

    def finish(self,ch):
        p=self.p;t=p.tracks[ch]
        if ch in p.cleared:return
        if t['near'] is not None:return self.original_finish(ch)
        center,radius=enclosing_circle(t['poly'])
        if radius<=p.cfg['clear_m']-1e-6 or not p.cfg.get('q4_strip_cover',True):
            return self.original_finish(ch)
        points,rectangles=clearing_route(t['poly'],t['origin'],t['deg'],p.pos,p.cfg)
        p.certificates.append(dict(channel=ch,center=center.tolist(),radius_m=radius,
                                   diameter_m=diameter(t['poly']),vertices=t['poly'].tolist()))
        if rectangles:self.routes+=1
        for point in points:
            if p.clear(point,ch):return
        raise RuntimeError('Certified optical strip cover exhausted')

    def run(self):
        p=self.p;points=BASE.ring_stations(p.cfg);visited=0
        while points or any(ch not in p.cleared for ch in p.tracks):
            pending=[ch for ch in p.tracks if ch not in p.cleared]
            costs={ch:self.target_cost(ch,points) for ch in pending}
            ch=min(pending,key=costs.get) if pending else None
            index=min(range(len(points)),key=lambda i:np.linalg.norm(points[i]-p.pos)) if points else None
            if index is not None and (ch is None or np.linalg.norm(points[index]-p.pos)<costs[ch]):
                station=points.pop(index);visited+=1
                channels=sorted((c for c in range(1,21) if c not in p.cleared and
                                 (c not in p.tracks or self.useful(station,c))),key=lambda c:(c!=p.channel,c))
                for c in channels:
                    response=p.measure(station,c)
                    if c in p.tracks:p.update(c,station,response)
                    elif response['measure_result']!='no_signal':p.make_track(c,station,response)
                    if p.cfg.get('q4_immediate_near',True) and response['measure_result']=='near':
                        if not p.clear(station,c):raise RuntimeError('near clear failed')
                        if len(p.cleared)==16:break
            else:
                if not self.ready(ch):
                    point,measure=self.destination(ch)
                    if measure:
                        response=p.measure(point,ch);p.update(ch,point,response)
                        if self.shared:p.shared_scan(exclude=ch)
                self.refine(ch);p.finish(ch)
                if self.shared:p.shared_scan()
            if len(p.cleared)==16:break
        return dict(cleared_count=len(p.cleared),visited_survey_points=visited,
                    termination='count_upper_bound' if len(p.cleared)==16 else 'full_coverage',
                    shared_attempts=p.shared_attempts,shared_hits=p.shared_hits)

    def target_cost(self,ch,stations):
        if self.p.cfg.get('q4_wait_once',False) and len(self.p.tracks[ch]['sample_points'])>1:
            self.wait=False
            try:return super().target_cost(ch,stations)
            finally:self.wait=self.original_wait
        return super().target_cost(ch,stations)

    def refine(self,ch):
        if ch in self.p.cleared:return
        if self.p.cfg.get('q4_scan_cost_gate',False):
            t=self.p.tracks[ch]
            if t['near'] is not None:return
            c,r=enclosing_circle(t['poly'])
            if not self.clear_m<r<=self.refine_max:return
            points,_=clearing_route(t['poly'],t['origin'],t['deg'],self.p.pos,self.p.cfg)
            budget=route_seconds(points,self.p.pos,self.p.cfg)
            travel=np.linalg.norm(c-self.p.pos)/self.p.cfg['speed_m_s']
            # Compare a complete cover to the optimistic cost of measuring then clearing.
            if budget<=travel+self.p.cfg['measure_s']+self.p.cfg['clear_failure_s']+10:return
        super().refine(ch)

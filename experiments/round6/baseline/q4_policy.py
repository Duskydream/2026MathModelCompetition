"""Q4 mixed routing with a continuous directional-coverage certificate."""
import math
import numpy as np
from model import clip, direction, enclosing_circle


def ring_stations(cfg):
    """Triangulate an enclosing dodecagon with edges below reception range.

    Every source is a convex combination of three stations within reception
    range. Any closed halfplane through that source contains a station.
    This proves coverage for every unknown antenna orientation.
    """
    radius=cfg['region_radius_m'];reception=cfg['receiver_radius_min_m']
    inner=999.*radius/1800.
    outer=radius/math.cos(math.pi/12)
    bound=max(inner,2*radius*math.tan(math.pi/12),
              math.sqrt(inner**2+outer**2-2*inner*radius))
    if not all(math.isfinite(v) and v>0 for v in (radius,reception)) or bound>=reception:
        raise ValueError('Q4 ring stations do not satisfy the reception certificate')
    angles=np.arange(12)*2*np.pi/12
    inner_points=inner*np.column_stack((np.cos(angles),np.sin(angles)))
    angles=angles+math.pi/12
    outer_points=outer*np.column_stack((np.cos(angles),np.sin(angles)))
    return list(np.vstack(([[0.,0.]],inner_points,outer_points)))


class Q4Planner:
    def __init__(self,policy):
        self.p=policy
        angles=np.arange(48)*2*np.pi/48
        self.normals=np.column_stack([np.cos(angles),np.sin(angles)])
        self.forward=policy.cfg.get('q4_second_forward_m',200.)
        self.lateral=policy.cfg.get('q4_second_lateral_m',100.)
        if not all(math.isfinite(v) and v>0 for v in (self.forward,self.lateral)):
            raise ValueError('Q4 second-point offsets must be positive and finite')

    def observe(self,position,ch,response):
        # Silence is compatible with a nearby directional transmitter.
        pass

    def constrain(self,ch):
        t=self.p.tracks[ch]
        if t['near'] is not None:return
        poly=clip(t['poly'],self.normals,
                  np.full(48,self.p.cfg['region_radius_m']+1e-7))
        if not len(poly):raise RuntimeError('Bearings contradict the target region')
        t['poly']=poly

    def destination(self,ch):
        p=self.p;t=p.tracks[ch]
        if t['near'] is not None:return t['near'],False
        center,radius=enclosing_circle(t['poly'])
        if radius<=20-1e-6 or t['count']>=2:return center,False
        u=direction(t['deg']);v=np.array([-u[1],u[0]])
        candidates=[t['origin']+self.forward*u+sign*self.lateral*v for sign in (-1,1)]
        return min(candidates,key=lambda q:np.linalg.norm(q-p.pos)+np.linalg.norm(q-center)),True

    def cost(self,ch):
        point,measure=self.destination(ch)
        center,_=enclosing_circle(self.p.tracks[ch]['poly'])
        return np.linalg.norm(point-self.p.pos)+(np.linalg.norm(point-center) if measure else 0.)

    def run(self):
        p=self.p;points=ring_stations(p.cfg);visited=0
        while points or any(ch not in p.cleared for ch in p.tracks):
            pending=[ch for ch in p.tracks if ch not in p.cleared]
            ch=min(pending,key=self.cost) if pending else None
            index=min(range(len(points)),key=lambda i:np.linalg.norm(points[i]-p.pos)) if points else None
            if index is not None and (ch is None or np.linalg.norm(points[index]-p.pos)<self.cost(ch)):
                station=points.pop(index);visited+=1
                channels=sorted((c for c in range(1,21) if c not in p.cleared),key=lambda c:(c!=p.channel,c))
                for c in channels:
                    response=p.measure(station,c)
                    if c in p.tracks:p.update(c,station,response)
                    elif response['measure_result']!='no_signal':p.make_track(c,station,response)
            else:
                point,measure=self.destination(ch)
                if measure:
                    response=p.measure(point,ch);p.update(ch,point,response)
                    p.shared_scan(exclude=ch)
                p.finish(ch);p.shared_scan()
            if len(p.cleared)==16:break
        return dict(cleared_count=len(p.cleared),visited_survey_points=visited,
                    termination='count_upper_bound' if len(p.cleared)==16 else 'full_coverage',
                    shared_attempts=p.shared_attempts,shared_hits=p.shared_hits)

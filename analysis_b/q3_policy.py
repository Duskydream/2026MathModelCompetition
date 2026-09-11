"""Q3-only mixed routing and conservative constraints from observed responses."""
import math
import numpy as np
from scipy.spatial import ConvexHull,QhullError
from model import clip,direction,enclosing_circle,survey_points

def outside_disk_hull(poly,center,radius):
    """Outer approximation of a convex polygon minus an open disk.

    Extremes of its convex hull are polygon vertices outside the disk or
    edge/circle intersections. Degenerate numerical cases retain the input.
    """
    points=[]
    squared_tolerance=1e-7*max(1.,radius*radius)
    for a,b in zip(poly,np.roll(poly,-1,axis=0)):
        delta=a-center;edge=b-a
        if delta@delta>=radius*radius-squared_tolerance:points.append(a)
        aa=edge@edge;bb=2*delta@edge;cc=delta@delta-radius*radius
        discriminant=bb*bb-4*aa*cc
        if aa>1e-16 and discriminant>=0:
            for fraction in ((-bb-math.sqrt(discriminant))/(2*aa),
                             (-bb+math.sqrt(discriminant))/(2*aa)):
                if -1e-9<=fraction<=1+1e-9:points.append(a+np.clip(fraction,0.,1.)*edge)
    if len(points)<3:return poly
    points=np.unique(np.asarray(points),axis=0)
    if len(points)<3:return poly
    try:return points[ConvexHull(points).vertices]
    except QhullError:return poly

class Q3Planner:
    def __init__(self,policy):
        self.p=policy
        self.silent={ch:[] for ch in range(1,21)}
        angles=np.arange(48)*2*np.pi/48
        self.region_normals=np.column_stack([np.cos(angles),np.sin(angles)])
        self.forward=policy.cfg.get('q3_second_forward_m',200.)
        self.lateral=policy.cfg.get('q3_second_lateral_m',100.)
        if not all(math.isfinite(x) and x>0 for x in (self.forward,self.lateral)):
            raise ValueError('Q3 second-point offsets must be positive and finite')
    def observe(self,position,ch,response):
        if response['measure_result']=='no_signal':
            self.silent[ch].append(np.asarray(position,float).copy())
    def constrain(self,ch):
        p=self.p;t=p.tracks[ch]
        if t['near'] is not None:return
        # Supporting halfplanes circumscribe the disk, never inscribe it.
        poly=clip(t['poly'],self.region_normals,
                  np.full(48,p.cfg['region_radius_m']+1e-7))
        if not len(poly):raise RuntimeError('Bearings contradict the target region')
        for station in self.silent[ch]:
            # In Q3 all transmitters are omnidirectional and radius >= R_min.
            # A slightly smaller excluded disk leaves numerical safety margin.
            poly=outside_disk_hull(poly,station,p.cfg['receiver_radius_min_m']-1e-4)
        t['poly']=poly
    def destination(self,ch):
        p=self.p;t=p.tracks[ch]
        if t['near'] is not None:return t['near'],False
        center,radius=enclosing_circle(t['poly'])
        if radius<=20-1e-6 or t['count']>=2:return center,False
        u=direction(t['deg']);v=np.array([-u[1],u[0]])
        candidates=[t['origin']+self.forward*u+sign*self.lateral*v for sign in (-1,1)]
        point=min(candidates,key=lambda q:np.linalg.norm(q-p.pos)+np.linalg.norm(q-center))
        return point,True
    def cost(self,ch):
        point,needs_measure=self.destination(ch)
        center,_=enclosing_circle(self.p.tracks[ch]['poly'])
        return np.linalg.norm(point-self.p.pos)+(np.linalg.norm(point-center) if needs_measure else 0.)
    def run(self):
        p=self.p;points=survey_points(3,p.cfg);visited=0
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
                point,needs_measure=self.destination(ch)
                if needs_measure:
                    response=p.measure(point,ch);p.update(ch,point,response)
                    p.shared_scan(exclude=ch)
                # Original certified clear and complete optical fallback.
                p.finish(ch);p.shared_scan()
            if len(p.cleared)==16:break
        return dict(cleared_count=len(p.cleared),visited_survey_points=visited,
                    termination='count_upper_bound' if len(p.cleared)==16 else 'full_coverage',
                    shared_attempts=p.shared_attempts,shared_hits=p.shared_hits)

"""Q4 selective measurements and bounded refinement with certified coverage."""
import math
import numpy as np
from model import clip, direction, enclosing_circle, diameter
from q4_optical import clearing_route, route_seconds


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


def hull_coverage_slack(stations,cfg,spacing=20.,margin=0.):
    """Minimum over a disk grid of the exact directional-coverage slack.

    A source at g with any orientation is detected from some station iff g lies
    in the convex hull of the stations within reception range of g. The slack is
    the distance from g to that hull boundary (negative outside), capped by the
    range margin; a rigorous continuum certificate additionally needs the slack
    to exceed spacing/sqrt(2) with margin=spacing/sqrt(2) (see
    experiments/q4_layout_search). This coarse check only guards against typos.
    """
    from scipy.spatial import ConvexHull
    S=np.asarray(stations,float);R=cfg['receiver_radius_min_m'];region=cfg['region_radius_m']
    xs=np.arange(-region,region+spacing,spacing);X,Y=np.meshgrid(xs,xs)
    G=np.column_stack((X.ravel(),Y.ravel()));G=G[np.hypot(G[:,0],G[:,1])<=region]
    angles=np.linspace(0,2*np.pi,int(2*np.pi*region/spacing)+1,endpoint=False)
    G=np.vstack((G,region*np.column_stack((np.cos(angles),np.sin(angles)))))
    D=np.linalg.norm(G[:,None,:]-S[None,:,:],axis=2);mask=D<=R-margin
    worst=math.inf;groups={}
    for i,row in enumerate(map(bytes,np.packbits(mask,axis=1))):groups.setdefault(row,[]).append(i)
    for idx in groups.values():
        T=S[mask[idx[0]]]
        if len(T)<3:return -math.inf
        eq=ConvexHull(T).equations;g=G[idx]
        worst=min(worst,float((-(g@eq[:,:2].T+eq[:,2]).max(axis=1)).min()))
    return worst


def survey_stations(cfg):
    """Survey layout: the analytic 25-station rings or an explicit certified list."""
    explicit=cfg.get('q4_station_list')
    if explicit is None:return ring_stations(cfg)
    S=np.asarray(explicit,float)
    if S.ndim!=2 or S.shape[1]!=2 or not np.all(np.isfinite(S)) or len(S)<3:
        raise ValueError('q4_station_list must be a finite list of planar points')
    if hull_coverage_slack(S,cfg)<0:
        raise ValueError('q4_station_list fails the directional coverage check')
    return list(S)


def polygon_distance(poly,point):
    """Euclidean distance to a nonempty convex polygon, including degeneracies."""
    poly=np.asarray(poly,float).reshape(-1,2);point=np.asarray(point,float)
    if not len(poly):raise ValueError('Empty target region')
    edges=np.roll(poly,-1,axis=0)-poly;delta=point-poly
    cross=edges[:,0]*delta[:,1]-edges[:,1]*delta[:,0]
    area2=np.sum(poly[:,0]*np.roll(poly[:,1],-1)-poly[:,1]*np.roll(poly[:,0],-1))
    if abs(area2)>1e-12 and (np.all(cross>=0) or np.all(cross<=0)):return 0.
    length2=np.sum(edges*edges,axis=1)
    fraction=np.divide(np.sum(delta*edges,axis=1),length2,out=np.zeros(len(poly)),where=length2>0)
    closest=poly+np.clip(fraction,0,1)[:,None]*edges
    return float(np.linalg.norm(closest-point,axis=1).min())


class Q4Planner:
    def __init__(self,policy):
        self.p=policy
        angles=np.arange(48)*2*np.pi/48
        self.normals=np.column_stack([np.cos(angles),np.sin(angles)])
        self.forward=policy.cfg.get('q4_second_forward_m',200.)
        self.lateral=policy.cfg.get('q4_second_lateral_m',100.)
        if not all(math.isfinite(v) and v>0 for v in (self.forward,self.lateral)):
            raise ValueError('Q4 second-point offsets must be positive and finite')
        cfg=policy.cfg
        self.clear_m=cfg['clear_m']
        self.selective=cfg.get('q4_selective_remeasure',True)
        self.wait=cfg.get('q4_wait_for_survey',True)
        self.shared=cfg.get('q4_shared_scan',True)
        self.help_m=cfg.get('q4_station_help_m',950.)
        self.help_distance=cfg.get('q4_help_distance','polygon')
        self.min_sine=cfg.get('q4_remeasure_min_sine',0.3)
        self.min_gap=cfg.get('q4_remeasure_min_gap_m',300.)
        self.stale_m=cfg.get('q4_wait_stale_m',1400.)
        self.refine_max=cfg.get('q4_refine_max_m',150.)
        self.wait_mode=cfg.get('q4_wait_mode','inner')
        self.strip_cover=cfg.get('q4_strip_cover',False)
        self.immediate_near=cfg.get('q4_immediate_near',False)
        self.scan_cost_gate=cfg.get('q4_scan_cost_gate',False)
        if not all(type(value) is bool for value in (self.selective,self.wait,self.shared)):
            raise ValueError('Q4 feature switches must be booleans')
        if not all(math.isfinite(v) and v>0 for v in (self.clear_m,self.help_m,self.min_gap,self.stale_m)):
            raise ValueError('Q4 distances must be positive and finite')
        if not math.isfinite(self.refine_max) or self.refine_max<0:
            raise ValueError('Q4 refinement radius must be non-negative and finite')
        if not math.isfinite(self.min_sine) or not 0<=self.min_sine<=1:
            raise ValueError('Q4 intersection sine must be between zero and one')
        if self.help_m>=cfg['receiver_radius_min_m'] or self.help_distance not in ('polygon','center'):
            raise ValueError('Invalid Q4 station help criterion')
        if self.wait_mode not in ('stale','inner','same_side','all_sides'):
            raise ValueError('Invalid Q4 waiting rule')
        if not all(type(value) is bool for value in (self.strip_cover,self.immediate_near,self.scan_cost_gate)):
            raise ValueError('Q4 optical feature switches must be booleans')

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
        if radius<=self.clear_m-1e-6 or t['count']>=2:return center,False
        u=direction(t['deg']);v=np.array([-u[1],u[0]])
        candidates=[t['origin']+self.forward*u+sign*self.lateral*v for sign in (-1,1)]
        return min(candidates,key=lambda q:np.linalg.norm(q-p.pos)+np.linalg.norm(q-center)),True

    def cost(self,ch):
        point,measure=self.destination(ch)
        center,_=enclosing_circle(self.p.tracks[ch]['poly'])
        return np.linalg.norm(point-self.p.pos)+(np.linalg.norm(point-center) if measure else 0.)

    def close_enough(self,station,ch):
        t=self.p.tracks[ch]
        if self.help_distance=='center':
            return np.linalg.norm(enclosing_circle(t['poly'])[0]-station)<=self.help_m
        return polygon_distance(t['poly'],station)<=self.help_m

    def useful(self,station,ch):
        if not self.selective:return True
        t=self.p.tracks[ch]
        if t['near'] is not None:return False
        center,radius=enclosing_circle(t['poly'])
        if radius<=self.clear_m-1e-6 or not self.close_enough(station,ch):return False
        for previous in t['sample_points']:
            a=center-previous;b=center-station
            sine=abs(a[0]*b[1]-a[1]*b[0])/max(np.linalg.norm(a)*np.linalg.norm(b),1e-9)
            if sine<self.min_sine and np.linalg.norm(station-previous)<self.min_gap:return False
        return True

    def ready(self,ch):
        t=self.p.tracks[ch]
        if t['near'] is not None:return True
        radius=enclosing_circle(t['poly'])[1]
        return radius<=max(self.clear_m-1e-6,self.refine_max)

    def target_cost(self,ch,stations):
        t=self.p.tracks[ch]
        if self.ready(ch):
            center=t['near'] if t['near'] is not None else enclosing_circle(t['poly'])[0]
            return np.linalg.norm(center-self.p.pos)
        # Waiting is bounded by the remaining finite survey and distance from first detection.
        if self.wait and np.linalg.norm(t['origin']-self.p.pos)<self.stale_m:
            if self.wait_mode=='inner' and np.linalg.norm(t['origin'])>=self.p.cfg['region_radius_m']:
                return self.cost(ch)
            for station in stations:
                if not self.close_enough(station,ch):continue
                if self.wait_mode in ('same_side','all_sides'):
                    probes=t['poly'] if self.wait_mode=='all_sides' else enclosing_circle(t['poly'])[0][None,:]
                    a=t['origin']-probes;b=station-probes
                    cosine=np.sum(a*b,axis=1)/np.maximum(np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1),1e-9)
                    if np.any(cosine<0.3):continue
                return math.inf
        return self.cost(ch)

    def refine(self,ch):
        t=self.p.tracks[ch];p=self.p
        if t['near'] is not None:return
        center,radius=enclosing_circle(t['poly'])
        if not self.clear_m<radius<=self.refine_max:return
        if self.scan_cost_gate:
            points,_=clearing_route(t['poly'],t['origin'],t['deg'],p.pos,p.cfg)
            budget=route_seconds(points,p.pos,p.cfg)
            travel=np.linalg.norm(center-p.pos)/p.cfg['speed_m_s']
            if budget<=travel+p.cfg['measure_s']+p.cfg['clear_failure_s']+10:return
        response=p.measure(center,ch);p.update(ch,center,response)
        if response['measure_result']!='direction':return
        new_center,new_radius=enclosing_circle(t['poly'])
        if new_radius<=self.clear_m-1e-6:return
        u=direction(response['svd_deg']);side=np.array([-u[1],u[0]])
        offset=3*self.clear_m
        candidates=(center+offset*side,center-offset*side)
        point=min(candidates,key=lambda q:np.linalg.norm(q-new_center))
        response=p.measure(point,ch);p.update(ch,point,response)

    def finish(self,ch):
        p=self.p;t=p.tracks[ch]
        if ch in p.cleared:return
        if t['near'] is not None:return p.finish(ch)
        center,radius=enclosing_circle(t['poly'])
        if radius<=self.clear_m-1e-6 or not self.strip_cover:return p.finish(ch)
        points,_=clearing_route(t['poly'],t['origin'],t['deg'],p.pos,p.cfg)
        p.certificates.append(dict(channel=ch,center=center.tolist(),radius_m=radius,
                                   diameter_m=diameter(t['poly']),vertices=t['poly'].tolist()))
        for point in points:
            if p.clear(point,ch):return
        raise RuntimeError('Certified optical strip cover exhausted')

    def run(self):
        p=self.p;points=survey_stations(p.cfg);visited=0
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
                    if self.immediate_near and response['measure_result']=='near':
                        if not p.clear(station,c):raise RuntimeError('near clear failed')
                        if len(p.cleared)==16:break
            else:
                if not self.ready(ch):
                    point,measure=self.destination(ch)
                    if measure:
                        response=p.measure(point,ch);p.update(ch,point,response)
                        if self.shared:p.shared_scan(exclude=ch)
                self.refine(ch)
                self.finish(ch)
                if self.shared:p.shared_scan()
            if len(p.cleared)==16:break
        return dict(cleared_count=len(p.cleared),visited_survey_points=visited,
                    termination='count_upper_bound' if len(p.cleared)==16 else 'full_coverage',
                    shared_attempts=p.shared_attempts,shared_hits=p.shared_hits)

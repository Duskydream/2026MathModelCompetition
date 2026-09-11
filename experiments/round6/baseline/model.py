"""Bounded-error geometry and online policy. No hidden-source access here."""
import itertools, math
import numpy as np
from scipy.optimize import linprog

def direction(deg):
    a=np.deg2rad(deg);return np.array([np.cos(a),np.sin(a)])

def bearing_halfplanes(point, deg, error=1.005):
    lo,hi=direction(deg-error),direction(deg+error)
    A=np.array([[lo[1],-lo[0]],[-hi[1],hi[0]]])
    return A,A@np.asarray(point)

def clip(poly,A,b,tol=1e-8):
    poly=np.asarray(poly,dtype=float).reshape(-1,2)
    for a,c in zip(A,b):
        if not len(poly):return poly
        new=[]
        for p,q in zip(poly,np.roll(poly,-1,axis=0)):
            fp,fq=a@p-c,a@q-c
            if fp<=tol:new.append(p)
            if (fp<=tol)!=(fq<=tol):new.append(p+(q-p)*fp/(fp-fq))
        poly=np.array(new).reshape(-1,2)
    return poly

def polygon_from_halfplanes(A,b):
    """Classify empty/unbounded/bounded without an artificial bounding box."""
    A,b=np.asarray(A,float),np.asarray(b,float)
    feasible=linprog([0,0],A_ub=A,b_ub=b,bounds=[(None,None)]*2,method='highs')
    if feasible.status==2:return {'status':'empty','vertices':np.empty((0,2)),'diameter':None}
    if not feasible.success:raise RuntimeError(feasible.message)
    for objective in ([1,0],[-1,0],[0,1],[0,-1]):
        r=linprog(objective,A_ub=A,b_ub=b,bounds=[(None,None)]*2,method='highs')
        if r.status==3:return {'status':'unbounded','vertices':np.empty((0,2)),'diameter':math.inf}
        if not r.success:raise RuntimeError(r.message)
    vertices=[]
    for i,j in itertools.combinations(range(len(A)),2):
        M=A[[i,j]]
        if abs(np.linalg.det(M))<1e-12:continue
        x=np.linalg.solve(M,b[[i,j]])
        if np.all(A@x<=b+1e-7) and not any(np.linalg.norm(x-v)<1e-7 for v in vertices):vertices.append(x)
    v=np.array(vertices).reshape(-1,2)
    if not len(v):raise RuntimeError('Numerically degenerate feasible polyhedron')
    c=v.mean(axis=0);v=v[np.argsort(np.arctan2(v[:,1]-c[1],v[:,0]-c[0]))]
    return {'status':'bounded','vertices':v,'diameter':diameter(v)}

def diameter(v):
    v=np.asarray(v);return float(np.sqrt(np.max(np.sum((v[:,None]-v[None,:])**2,axis=2))))

def enclosing_circle(v):
    """Exact candidate enumeration; at most three support vertices in 2D."""
    v=np.asarray(v);best=(None,math.inf)
    candidates=list(v)
    candidates.extend((p+q)/2 for p,q in itertools.combinations(v,2))
    for p,q,r in itertools.combinations(v,3):
        M=2*np.array([q-p,r-p])
        if abs(np.linalg.det(M))>1e-10:
            candidates.append(np.linalg.solve(M,np.array([q@q-p@p,r@r-p@p])))
    for c in candidates:
        rad=float(np.max(np.linalg.norm(v-c,axis=1)))
        if rad<best[1]:best=(c,rad)
    return best

def initial_polygon(p,deg,cfg):
    u=direction(deg);v=np.array([-u[1],u[0]])
    r=cfg['receiver_radius_max_m'];w=r*np.tan(np.deg2rad(cfg['bearing_bound_deg']))
    return np.array([p,p+r*u-w*v,p+r*u+w*v])

def optical_cells(poly,origin,deg,h):
    """Every square intersecting polygon; square circumradius h/sqrt(2)."""
    u=direction(deg);v=np.array([-u[1],u[0]]);B=np.stack([u,v],axis=1)
    local=(poly-origin)@B
    lows=np.floor(local.min(axis=0)/h-.5).astype(int)
    highs=np.ceil(local.max(axis=0)/h+.5).astype(int)
    cells=[]
    A=np.array([[1,0],[-1,0],[0,1],[0,-1]])
    for i in range(lows[0],highs[0]+1):
        js=list(range(lows[1],highs[1]+1))
        if i%2:js.reverse()
        for j in js:
            c=np.array([i*h,j*h]);b=np.array([c[0]+h/2,-c[0]+h/2,c[1]+h/2,-c[1]+h/2])
            if len(clip(local,A,b)):cells.append(origin+B@c)
    return cells

def triangular_survey_points(cfg):
    """Vertices of every closed triangular cell intersecting the target disk.

    The centroid of one cell is at the origin. See docs/experiment2_report.md.
    Keep exterior vertices: clipping stations to the disk breaks direction coverage.
    """
    radius=cfg['region_radius_m']
    spacing=cfg.get('q4_triangle_spacing_m',950)
    reception=cfg['receiver_radius_min_m']
    if not all(math.isfinite(v) and v>0 for v in (radius,spacing,reception)):
        raise ValueError('Triangle survey requires positive finite distances')
    if spacing>=reception:
        raise ValueError('Triangle spacing must be below minimum reception radius')
    height=spacing*math.sqrt(3)/2
    offset=np.array([spacing/2,height/3])
    def vertex(i,j):
        return np.array([spacing*(i+j/2),height*j])-offset
    # Includes a full cell beyond each disk bounding-box edge.
    rows=math.ceil((radius+height/3)/height)+1
    columns=math.ceil(radius/spacing+rows/2+0.5)+1
    tolerance=1e-9*max(1.,radius,spacing)
    selected=set()
    for j in range(-rows,rows+1):
        for i in range(-columns,columns+1):
            for ids in (((i,j),(i+1,j),(i,j+1)),
                        ((i+1,j),(i+1,j+1),(i,j+1))):
                a=np.array([vertex(*ij) for ij in ids])
                edge=np.roll(a,-1,axis=0)-a
                cross=edge[:,0]*(-a[:,1])-edge[:,1]*(-a[:,0])
                inside=bool(np.all(cross>=0))
                fraction=np.clip(-np.sum(a*edge,axis=1)/np.sum(edge*edge,axis=1),0,1)
                closest=a+fraction[:,None]*edge
                if inside or np.any(np.sum(closest*closest,axis=1)<=(radius+tolerance)**2):
                    selected.update(ids)
    return sorted((vertex(*ij) for ij in selected),key=lambda p:(p[0],p[1]))

def survey_points(question,cfg):
    if question==3:
        layout=cfg.get('q3_survey_layout','grid')
        if layout=='hexagon':
            # Center plus six ring stations; validate the continuous bound below.
            # See docs/experiment3_report.md for the configurable-ring proof.
            radius=cfg['region_radius_m']
            if not math.isfinite(radius) or radius<=0 or radius/2>cfg['receiver_radius_min_m']:
                raise ValueError('Hexagon survey requires 0 < region radius <= 2 * minimum reception radius')
            ring=cfg.get('q3_ring_radius_m',radius*math.cos(math.pi/6))
            if not math.isfinite(ring) or not 0<ring<=math.sqrt(3)*radius:
                raise ValueError('Q3 ring radius must be positive, finite, and within the coverage geometry')
            # Extrema: Voronoi junction and the target-circle sector bisector.
            worst=max(ring/math.sqrt(3),math.sqrt(radius**2+ring**2-math.sqrt(3)*radius*ring))
            if worst>cfg['receiver_radius_min_m']-1e-6:
                raise ValueError('Q3 ring does not guarantee minimum-radius coverage')
            return [np.zeros(2)]+[ring*direction(60*k) for k in range(6)]
        if layout!='grid':raise ValueError(f'Unknown Q3 survey layout: {layout}')
    if question==4:
        layout=cfg.get('q4_survey_layout','grid')
        if layout=='triangular':return triangular_survey_points(cfg)
        if layout!='grid':raise ValueError(f'Unknown Q4 survey layout: {layout}')
    h=cfg[f'q{question}_grid_m'];n=math.ceil(cfg['region_radius_m']/h)
    return [np.array([i*h,j*h],float) for i in range(-n,n+1) for j in range(-n,n+1)]

class Policy:
    def __init__(self,transport,cfg,question,strategy='triangulate'):
        self.io=transport;self.cfg=cfg;self.question=question;self.strategy=strategy
        self.pos=np.zeros(2);self.channel=1;self.cleared=set();self.observations={};self.certificates=[]
    def measure(self,p,ch):
        r=self.io.measure(p,ch);self.pos=np.array(p);self.channel=ch;return r
    def clear(self,p,ch):
        r=self.io.clear(p,ch);self.pos=np.array(p)
        if r['clear_result']=='success':self.cleared.add(ch);return True
        return False
    def locate(self,ch,p,r):
        if r['measure_result']=='near':
            if not self.clear(p,ch):raise RuntimeError('near contradicts clear')
            return
        deg=r['svd_deg'];poly=initial_polygon(p,deg,self.cfg)
        if self.strategy=='triangulate':
            u=direction(deg);v=np.array([-u[1],u[0]])
            q=p+self.cfg['second_forward_m']*u+self.cfg['second_lateral_m']*v
            r2=self.measure(q,ch)
            if r2['measure_result']=='near':
                if not self.clear(q,ch):raise RuntimeError('near contradicts clear')
                return
            if r2['measure_result']=='direction':
                A,b=bearing_halfplanes(q,r2['svd_deg'],self.cfg['bearing_bound_deg']);poly=clip(poly,A,b)
                if not len(poly):raise RuntimeError('Inconsistent bearing bounds; stop rather than fabricate estimate')
        center,radius=enclosing_circle(poly)
        self.certificates.append({'channel':ch,'center':center.tolist(),'radius_m':radius,'diameter_m':diameter(poly),'vertices':poly.tolist()})
        if radius<=self.cfg['clear_m']-1e-6:
            if not self.clear(center,ch):raise RuntimeError('Certified disk clear failed')
            return
        cells=optical_cells(poly,p,deg,self.cfg['optical_grid_m'])
        if cells and np.linalg.norm(cells[-1]-self.pos)<np.linalg.norm(cells[0]-self.pos):cells.reverse()
        for cell in cells:
            if self.clear(cell,ch):return
        raise RuntimeError('Optical cover exhausted without success')
    def run(self):
        points=survey_points(self.question,self.cfg);visited=0
        while points:
            k=min(range(len(points)),key=lambda i:float(np.sum((points[i]-self.pos)**2)))
            p=points.pop(k);visited+=1
            channels=[c for c in range(1,21) if c not in self.cleared]
            channels.sort(key=lambda c:(c!=self.channel,c))
            hits=[]
            for ch in channels:
                r=self.measure(p,ch)
                if r['measure_result']!='no_signal':hits.append((ch,p.copy(),r))
            for ch,s,r in hits:
                if ch not in self.cleared:self.locate(ch,s,r)
            if len(self.cleared)==16:break
        return {'cleared_count':len(self.cleared),'visited_survey_points':visited,'termination':'count_upper_bound' if len(self.cleared)==16 else 'full_coverage'}

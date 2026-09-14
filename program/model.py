"""有界误差交会定位的几何工具与在线策略基线。

本模块的每一步决策只使用机器狗可观测的读数（方位、near、no_signal），
不读取源的真实坐标，与题设“部分可观测”一致。示向度统一处理成前向楔形：
多站交会时背向区域被排除，交集只剩真实位置所在的一块（见 bearing_halfplanes
与 clip）。观测带界，因此可行域由误差范围对应的半平面交集描述，认证判据
只依赖最小包围圆。
"""
import itertools, math
import numpy as np
from scipy.optimize import linprog

def direction(deg):
    a=np.deg2rad(deg);return np.array([np.cos(a),np.sin(a)])

def bearing_halfplanes(point, deg, error=1.005):
    """以方位角为中心、两侧各展宽 error 度，给出两条前向半平面的约束。"""
    lo,hi=direction(deg-error),direction(deg+error)
    A=np.array([[lo[1],-lo[0]],[-hi[1],hi[0]]])
    return A,A@np.asarray(point)

def clip(poly,A,b,tol=1e-8):
    """用半平面组 A x ≤ b 逐边裁剪多边形；tol 为落在边界上的容差。"""
    # FIXME: 逐边裁剪在顶点很多时较慢，尚未替换为排序增量式半平面交。
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
    """判定半平面交的类型（空/无界/有界）并返回顶点与直径。

    先用线性规划沿 ±x、±y 四个方向探测目标函数是否有下界，任一方向无下界
    即判 unbounded，避免把无界区域当成有界而低估直径。有界时枚举两两约束
    直线的交点作为候选顶点，过滤后按极角排序。
    """
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
    """顶点集合的直径：两两欧氏距离的最大值。"""
    v=np.asarray(v);return float(np.sqrt(np.max(np.sum((v[:,None]-v[None,:])**2,axis=2))))

def enclosing_circle(v):
    """最小包围圆：枚举全部候选圆心，二维情形最多由 3 个支撑顶点确定。

    候选包括各顶点、各顶点对的中点，以及任意不共线三点确定的外接圆心，
    逐一代入取到最远顶点的距离作为半径并保留最小者。这样得到的半径是可行
    域的真实外接圆半径，直接供清除判据使用；三角形一类可行域若用外接矩形
    中心近似会被低估，从而误判为可一次清除。
    """
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
    """由首个方位读数给出初始前向楔形：沿 deg 前进到接收距离，按角度界张开。"""
    u=direction(deg);v=np.array([-u[1],u[0]])
    r=cfg['receiver_radius_max_m'];w=r*np.tan(np.deg2rad(cfg['bearing_bound_deg']))
    return np.array([p,p+r*u-w*v,p+r*u+w*v])

def optical_cells(poly,origin,deg,h):
    """返回与多边形相交的每个方格（输出格心坐标）；方格外接圆半径 h/√2。"""
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
    """目标圆内所有闭合三角网格单元的顶点，用于第四问早期的三角布局。

    单元直径小于最小接收距离时，圆内任一点都落在某个单元顶点的接收范围内，
    由此得到方向覆盖的充分条件；它要求相邻站距都足够小，站数因此压不下去，
    后来改用凸包充要条件。质心单元落在原点，环半径的取值见
    docs/experiment2_report.md。圆外顶点一并保留：把测站裁剪进圆内会破坏
    方向覆盖。
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
    # 每个方向都多取一整格，避免边界处的单元被漏掉。
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

def worst_uncovered_distance(stations,region,spacing=5.):
    """任一圆盘点到自己最近测站的最大距离（粗网格 + 圆周边界采样）。

    粗网格会把最坏点漏在格间，故沿目标圆周按 spacing 再补一圈采样；返回值
    再按格对角线的一半 h/√2 外扩，得到连续域上的保守上界。
    """
    stations=np.asarray(stations,float)
    xs=np.arange(-region,region+spacing,spacing);X,Y=np.meshgrid(xs,xs)
    points=np.column_stack((X.ravel(),Y.ravel()));points=points[np.hypot(points[:,0],points[:,1])<=region]
    angles=np.linspace(0,2*np.pi,int(2*np.pi*region/spacing)+1,endpoint=False)
    points=np.vstack((points,region*np.column_stack((np.cos(angles),np.sin(angles)))))
    worst=0.
    for start in range(0,len(points),100000):
        block=points[start:start+100000]
        worst=max(worst,float(np.min(np.linalg.norm(block[:,None,:]-stations[None,:,:],axis=2),axis=1).max()))
    return worst+spacing/math.sqrt(2)

def survey_points(question,cfg):
    if question==3:
        layout=cfg.get('q3_survey_layout','grid')
        if layout=='hexagon':
            # 圆心站加六个环站；连续域覆盖上界在下方即时校验。
            # 环半径的取值区间见 docs/experiment3_report.md。
            radius=cfg['region_radius_m']
            if not math.isfinite(radius) or radius<=0 or radius/2>cfg['receiver_radius_min_m']:
                raise ValueError('Hexagon survey requires 0 < region radius <= 2 * minimum reception radius')
            ring=cfg.get('q3_ring_radius_m',radius*math.cos(math.pi/6))
            if not math.isfinite(ring) or not 0<ring<=math.sqrt(3)*radius:
                raise ValueError('Q3 ring radius must be positive, finite, and within the coverage geometry')
            # 极值点：Voronoi 三重点，以及目标圆上两环点角平分方向的点。
            worst=max(ring/math.sqrt(3),math.sqrt(radius**2+ring**2-math.sqrt(3)*radius*ring))
            if worst>cfg['receiver_radius_min_m']-1e-6:
                raise ValueError('Q3 ring does not guarantee minimum-radius coverage')
            return [np.zeros(2)]+[ring*direction(60*k) for k in range(6)]
        if layout=='six':
            # 实验性、无覆盖保证：半径比为 1.8 的目标圆，六个测站覆盖不了，
            # 边界处总有一圈薄带超过最小接收半径，因此存在极小漏检概率。
            # 调用方须显式接受这一风险并给出 q3_uncovered_tolerance_m；
            # 详见 docs/q3_six_station_trial.md。
            stations=np.asarray(cfg.get('q3_station_list'),float)
            if stations.ndim!=2 or stations.shape[1]!=2 or not np.all(np.isfinite(stations)) or len(stations)<3:
                raise ValueError('Q3 six-station layout requires q3_station_list with finite planar points')
            allowed=cfg.get('q3_uncovered_tolerance_m')
            if not (isinstance(allowed,(int,float)) and math.isfinite(allowed) and 0<allowed<=100):
                raise ValueError('Q3 six-station layout requires an explicit q3_uncovered_tolerance_m in (0,100]')
            worst=worst_uncovered_distance(stations,cfg['region_radius_m'])
            if worst>cfg['receiver_radius_min_m']+allowed:
                raise ValueError(f'Q3 station list leaves points {worst:.1f} m from every station, beyond the declared tolerance')
            return list(stations)
        if layout!='grid':raise ValueError(f'Unknown Q3 survey layout: {layout}')
    if question==4:
        layout=cfg.get('q4_survey_layout','grid')
        if layout=='triangular':return triangular_survey_points(cfg)
        if layout!='grid':raise ValueError(f'Unknown Q4 survey layout: {layout}')
    h=cfg[f'q{question}_grid_m'];n=math.ceil(cfg['region_radius_m']/h)
    return [np.array([i*h,j*h],float) for i in range(-n,n+1) for j in range(-n,n+1)]

class Policy:
    """基线策略：逐站扫描，用观测半平面逐步收缩目标可行域并认证清除。"""
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
        """在测得方位的一站上建立并收缩可行域，随后认证或光学清除该频道。"""
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
        """按最近邻遍历测站，命中源后交 locate 处理，直到清满或走完全部测站。"""
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

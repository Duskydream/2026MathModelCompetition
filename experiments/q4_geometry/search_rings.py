"""Offline sufficient continuous triangle coverage certificate for ring layouts."""
import math
import numpy as np
from scipy.spatial import Delaunay, ConvexHull

R=1800.
def ring(n,r,offset):
    a=np.arange(n)*2*np.pi/n+offset
    return r*np.column_stack((np.cos(a),np.sin(a)))

def ring25_points(cfg):
    """Continuous proof: disk lies inside outer regular dodecagon.

    Center plus inner dodecagon and alternating outer dodecagon triangulate
    this polygon. At R=1800, inner radius=999, every triangle has diameter
    at most 999 (< minimum receiver radius 1000). The outer edge is
    2 R tan(15 degrees)=964.617..., and each inner-to-outer edge is
    sqrt(999**2+(R/cos(15 degrees))**2-2*999*R)<1000.
    Every source is a convex combination of triangle vertices within range;
    any closed oriented halfplane at the source contains at least one vertex.
    """
    r=cfg['region_radius_m'];inner=999.*r/1800.
    outer=r/math.cos(math.pi/12)
    bound=max(inner,2*r*math.tan(math.pi/12),
              math.sqrt(inner**2+outer**2-2*inner*r))
    if bound>=cfg['receiver_radius_min_m']:
        raise ValueError('Ring layout does not satisfy reception certificate')
    return list(np.vstack(([[0.,0.]],ring(12,inner,0),ring(12,outer,math.pi/12))))

def certificate(points):
    hull=ConvexHull(points)
    if np.any(hull.equations[:,2]>-R+1e-7):return math.inf
    worst=0.
    for ids in Delaunay(points).simplices:
        tri=points[ids]
        cand=[p for p in tri if p@p<=R*R+1e-7]
        for a,b in zip(tri,np.roll(tri,-1,axis=0)):
            e=b-a;aa=e@e;bb=2*a@e;cc=a@a-R*R
            disc=bb*bb-4*aa*cc
            if disc>=0:
                for t in ((-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa)):
                    if 0<=t<=1:cand.append(a+t*e)
        # Circular-arc maxima for distance to each triangle vertex.
        inverse=np.linalg.inv(np.stack((tri[1]-tri[0],tri[2]-tri[0]),axis=1))
        for v in tri:
            if np.linalg.norm(v)>1e-9:
                p=-R*v/np.linalg.norm(v);w=inverse@(p-tri[0])
                if w.min()>=-1e-9 and w.sum()<=1+1e-9:cand.append(p)
        if cand:
            worst=max(worst,float(np.linalg.norm(np.array(cand)[:,None]-tri[None],axis=2).max()))
    return worst

if __name__=='__main__':
    best={}
    for ni in range(6,13):
        for no in range(10,17):
            n=1+ni+no
            if n>25:continue
            for ri in np.arange(650.,1101.,50.):
                for ro in np.arange(1850.,2301.,50.):
                    for offset in [0.,np.pi/no]:
                        pts=np.vstack(([[0.,0.]],ring(ni,ri,0),ring(no,ro,offset)))
                        bound=certificate(pts)
                        if bound<best.get(n,(math.inf,))[0]:
                            best[n]=(bound,ni,no,ri,ro,offset)
    print(best,flush=True)
    p=np.vstack(([[0.,0.]],ring(12,999,0),ring(12,R/math.cos(math.pi/12),math.pi/12)))
    print('25 closed proof',certificate(p),flush=True)

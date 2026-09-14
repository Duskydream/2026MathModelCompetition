"""第四问光学清除的连续域覆盖，独立于射频可见性。

把多边形按首测方向切成窄条，条内再切矩形；矩形四角落在同一个清除盘内时，
由凸性整个矩形都在盘内，沿矩形中心布点即可覆盖该块区域。条带越宽列数越少、
单列却越长，路径未必更短，因此条带路线与方格路线都用 route_seconds 折算成
时间，取更省者（见 clearing_route）。
"""
import math
import numpy as np
from model import clip, direction, optical_cells


def route_seconds(points,start,cfg):
    """把一条清除路线的移动与清除时间折算成虚拟秒。"""
    points=np.asarray(points,float)
    length=float(np.linalg.norm(points[0]-start)+np.linalg.norm(np.diff(points,axis=0),axis=1).sum())
    return length/cfg['speed_m_s']+len(points)*cfg['clear_failure_s']


def strip_cover(poly,origin,deg,width,radius):
    """把多边形按条带切分、条内再切行，使每个矩形四角都落在同一个清除盘内。"""
    u=direction(deg);basis=np.stack([u,[-u[1],u[0]]],axis=1)
    local=(np.asarray(poly)-origin)@basis
    lo,hi=local[:,0].min(),local[:,0].max()
    count=max(1,math.ceil((hi-lo)/width))
    cuts=np.linspace(lo,hi,count+1);columns=[];certificates=[]
    for left,right in zip(cuts[:-1],cuts[1:]):
        section=clip(local,[[1.,0.],[-1.,0.]],[right,-left])
        if not len(section):continue
        bottom,top=section[:,1].min(),section[:,1].max()
        half_x=(right-left)/2
        max_height=2*math.sqrt(max(0.,radius*radius-half_x*half_x))
        if max_height<=0:raise ValueError('Strip wider than clear diameter')
        rows=max(1,math.ceil((top-bottom)/max_height))
        ycuts=np.linspace(bottom,top,rows+1)
        centers=[]
        for lower,upper in zip(ycuts[:-1],ycuts[1:]):
            center=np.array([(left+right)/2,(lower+upper)/2])
            corners=np.array([[left,lower],[right,lower],[right,upper],[left,upper]])
            assert np.max(np.linalg.norm(corners-center,axis=1))<=radius+1e-7
            centers.append(origin+basis@center)
            certificates.append(dict(center=(origin+basis@center).tolist(),
                                     corners=(origin+corners@basis.T).tolist()))
        columns.append(centers)
    return columns,certificates


def order_columns(columns,start):
    """逐条选择较近的一端进入，把各列拼成一条连续路线。"""
    path=[];position=np.asarray(start)
    for column in columns:
        if np.linalg.norm(column[-1]-position)<np.linalg.norm(column[0]-position):column=column[::-1]
        path.extend(column);position=column[-1]
    return path


def clearing_route(poly,origin,deg,start,cfg):
    """方格路线与四种条带宽度的条带路线比较，返回时间更短者及其矩形证书。"""
    old=optical_cells(poly,origin,deg,cfg['optical_grid_m'])
    if np.linalg.norm(old[-1]-start)<np.linalg.norm(old[0]-start):old.reverse()
    best=old;cost=route_seconds(old,start,cfg);certificate=None
    radius=cfg['clear_m']-0.1
    if radius<=0:return best,certificate
    for fraction in (1.25,1.5,1.7,1.9):
        columns,rectangles=strip_cover(poly,origin,deg,fraction*radius,radius)
        for ordered in (columns,columns[::-1]):
            candidate=order_columns(ordered,start)
            candidate_cost=route_seconds(candidate,start,cfg)
            if candidate_cost<cost-1e-7:
                best,cost,certificate=candidate,candidate_cost,rectangles
    return best,certificate

"""在“方向覆盖”的带余量证书下搜索第四问测站布局。

证书：对 1800 m 圆盘上每一点 g，存在测站子集 T，使每个 s 属于 T 时满足
|s-g| ≤ R - m，且 g 落在 conv(T) 内、到其边界距离 ≥ m。于是过 g 附近任意点
的任一闭半平面内都含一个距其 R 内的测站，即 g 处任意天线朝向都能被看到。
当最小余量超过网格步长时，离散网格证书即可推广到连续域（h/√2）。

搜索以最小余量 Slack 为目标（objective 取网格上的最小 slack），从环形种子
出发做局部随机扰动，再用 2-opt 收紧巡站长度；减站过程按此逐档比较。
"""
import sys,math,json,time
import numpy as np
from scipy.spatial import ConvexHull

R=1000.;REGION=1800.

def grid(h):
    xs=np.arange(-REGION,REGION+h,h);X,Y=np.meshgrid(xs,xs);G=np.column_stack((X.ravel(),Y.ravel()))
    G=G[np.hypot(G[:,0],G[:,1])<=REGION]
    ring=np.linspace(0,2*np.pi,int(2*np.pi*REGION/h)+1,endpoint=False)
    return np.vstack((G,REGION*np.column_stack((np.cos(ring),np.sin(ring)))))

def slack(S,G,m):
    """Min over grid of hull slack using stations within R-m; -inf if fewer than 3."""
    S=np.asarray(S);D=np.linalg.norm(G[:,None,:]-S[None,:,:],axis=2);mask=D<=R-m
    packed=np.packbits(mask,axis=1);keys={}
    for i,row in enumerate(map(bytes,packed)):keys.setdefault(row,[]).append(i)
    third=np.sort(D,axis=1)[:,2] if S.shape[0]>=3 else np.full(len(G),np.inf)
    out=(R-m)-third   # negative when fewer than three stations are in range
    for row,idx in keys.items():
        T=S[mask[idx[0]]]
        if len(T)<3:continue
        try:eq=ConvexHull(T).equations
        except Exception:out[idx]=np.minimum(out[idx],-1.);continue
        g=G[idx];out[idx]=np.minimum(out[idx],-(g@eq[:,:2].T+eq[:,2]).max(axis=1))
    return out

def objective(S,G,m):
    s=slack(S,G,m);k=int(np.argmin(s));return float(s[k]),G[k]

def tour(S):
    """从原点出发的最近邻巡回，再用 2-opt 收紧，返回总长度。"""
    S=[np.zeros(2)]+[np.asarray(p) for p in S];n=len(S);order=[0];left=set(range(1,n))
    while left:
        k=min(left,key=lambda i:np.linalg.norm(S[i]-S[order[-1]]));order.append(k);left.remove(k)
    L=lambda o:sum(np.linalg.norm(S[o[i]]-S[o[i+1]]) for i in range(len(o)-1))
    improved=True
    while improved:
        improved=False
        for i in range(1,n-1):
            for j in range(i+1,n):
                new=order[:i]+order[i:j+1][::-1]+order[j+1:]
                if L(new)<L(order)-1e-9:order=new;improved=True
    return L(order)

def ring(n,r,phase=0.):
    a=np.arange(n)*2*np.pi/n+phase;return list(np.column_stack((r*np.cos(a),r*np.sin(a))))

def seeds(N,rng):
    out=[]
    for n_out in (9,10,11,12):
        for center in (0,1):
            n_in=N-n_out-center
            if n_in<3:continue
            for r_in in (700,850,950):
                for r_out in (1850,1900,1950):
                    out.append(([np.zeros(2)] if center else [])+ring(n_in,r_in,rng.uniform(0,2*np.pi))+ring(n_out,r_out,rng.uniform(0,2*np.pi)))
    return out

def optimize(N,budget_s,seed=0,m=20.,h=40.):
    """在预算内从多个环形种子出发，用随机扰动最大化网格上的最小余量。"""
    rng=np.random.default_rng(seed);G=grid(h);best=None;t0=time.time()
    cands=seeds(N,rng)
    scored=sorted(((objective(S,G,m)[0],i) for i,S in enumerate(cands)),reverse=True)[:6]
    pool=[np.array(cands[i]) for _,i in scored]
    while time.time()-t0<budget_s:
        for S in pool:
            cur,_=objective(S,G,m)
            for _ in range(40):
                step=rng.choice([15.,40.,100.]);T=S.copy()
                k=rng.integers(len(S)) if rng.random()<0.7 else slice(None)
                T[k]+=rng.normal(0,step,size=np.shape(T[k]))
                val,_=objective(T,G,m)
                if val>cur:S[:]=T;cur=val
            if best is None or cur>best[0]:best=(cur,S.copy())
            if time.time()-t0>budget_s:break
    return best

if __name__=='__main__':
    N=int(sys.argv[1]);budget=float(sys.argv[2]);seed=int(sys.argv[3]) if len(sys.argv)>3 else 0
    val,S=optimize(N,budget,seed)
    fine,worst=objective(S,grid(6.),20.)
    print(json.dumps(dict(N=N,coarse_slack=val,fine_slack=fine,worst=worst.tolist(),tour_m=tour(list(S)),stations=S.tolist())))

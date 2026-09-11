"""Reproduce all local results, assertions, saved cases, logs and figures."""
from pathlib import Path
import csv, gzip, hashlib, itertools, json, math, platform, sys, time
import numpy as np
import scipy
from PIL import Image, ImageDraw, ImageFont
from model import *
from simulator import LocalSimulator,generate

BASE=Path(__file__).resolve().parent;OUT=BASE/'results';OUT.mkdir(exist_ok=True)
CFG=json.loads((BASE/'config.json').read_text());SEED=CFG['seed']

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def csvsave(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def validate(sim,policy,sources):
    pos=np.zeros(2);ch=1;t=0;removed=set();lookup={s['channel']:s for s in sources}
    for row in sim.log:
        p=np.array(row['position']);c=row['channel'];t+=np.linalg.norm(p-pos)/5;pos=p
        if row['action']=='measure':t+=5+(c!=ch);ch=c
        else:
            success=row['response']['clear_result']=='success';t+=5 if success else 3
            if success:
                assert c not in removed and np.linalg.norm(p-lookup[c]['position'])<=20+1e-8
                removed.add(c)
        assert abs(t-row['response']['virtual_time_s'])<1e-6
    for cert in policy.certificates:
        source=np.array(lookup[cert['channel']]['position'])
        assert np.linalg.norm(source-cert['center'])<=cert['radius_m']+1e-6
        v=np.array(cert['vertices'])
        for a,b in zip(v,np.roll(v,-1,axis=0)):
            assert np.linalg.det(np.stack([b-a,source-a]))>=-1e-5
    assert len(removed)==len(sources)==len(policy.cleared)
    assert abs(sum(sim.parts.values())-t)<1e-6

def geometry_checks():
    D=40.;tri=np.array([[0,0],[D,0],[D/2,D*np.sqrt(3)/2]])
    stations=[];AA=[];bb=[]
    for a,b in zip(tri,np.roll(tri,-1,axis=0)):
        u=(b-a)/D;p=a-1100*u;deg=np.degrees(np.arctan2(u[1],u[0]))+1
        A,z=bearing_halfplanes(p,deg,1);AA.extend(A);bb.extend(z);stations.append(dict(point=p.tolist(),bearing_deg=float(deg%360)))
    region=polygon_from_halfplanes(AA,bb);center,radius=enclosing_circle(region['vertices'])
    assert abs(region['diameter']-40)<1e-6 and abs(radius-40/np.sqrt(3))<1e-6
    A,b=bearing_halfplanes([0,0],0,1)
    assert polygon_from_halfplanes(A,b)['status']=='unbounded'
    assert polygon_from_halfplanes([[1,0],[-1,0]],[0,-1])['status']=='empty'
    segment=polygon_from_halfplanes([[1,0],[-1,0],[0,1],[0,-1]],[1,0,0,0]);assert abs(segment['diameter']-1)<1e-8
    p=polygon_from_halfplanes([[1,0],[-1,0],[0,1],[0,-1]],[0,0,0,0]);assert p['diameter']==0
    sim=LocalSimulator([],CFG)
    sim.measure([300,400],1);sim.measure([300,400],2);sim.clear([300,0],3);sim.measure([300,0],2)
    assert sim.time==199 and sim.channel==2
    s=[dict(channel=1,position=[50,0],radius_m=1000,orientation_deg=None)]
    sim=LocalSimulator(s,CFG,seed=SEED);a=sim.measure([0,0],1);b=sim.measure([0,0],1);assert a['svd_deg']==b['svd_deg']
    # Exact thresholds, bearing wrapping, and direction-independent optical clear.
    sim=LocalSimulator([dict(channel=1,position=[0,0],radius_m=1000,orientation_deg=0)],CFG,noise='zero')
    assert sim.measure([1000,0],1)['measure_result']=='direction'
    assert sim.measure([1000.01,0],1)['measure_result']=='no_signal'
    assert sim.measure([0,5],1)['measure_result']=='near'
    assert sim.measure([-5,0],1)['measure_result']=='no_signal'
    assert sim.clear([-20,0],1)['clear_result']=='success'
    assert sim.clear([-20,0],1)['clear_result']=='no_target_in_range'
    # Return rounding can cross 360 degrees.
    sim=LocalSimulator([dict(channel=1,position=[100,-.001],radius_m=1000,orientation_deg=None)],CFG,noise='zero')
    assert sim.measure([0,0],1)['svd_deg']==0
    result={'equilateral_vertices':region['vertices'].tolist(),'stations':stations,'diameter_m':region['diameter'],'minimum_circle_radius_m':radius,'diameter_half_m':region['diameter']/2,'circle_center':center.tolist(),'protocol_example_s':199,'empty_unbounded_segment_point_checks':'passed','threshold_repeat_rounding_checks':'passed'}
    save('geometry.json',result);return result

def second_point_study():
    cfg=CFG;eps=np.deg2rad(cfg['bearing_bound_deg']);poly=initial_polygon(np.zeros(2),0,cfg);rows=[]
    for a,b in itertools.product([250,500,650,750],[100,250,450]):
        q=np.array([a,b]);safe=np.linalg.norm(q)<=1000 and q@q<=2000*(a*np.cos(eps)-abs(b)*np.sin(eps))
        worst=0.;radii=[]
        for r,theta,e in itertools.product(np.linspace(5.1,1500,21),[-eps,0,eps],[-cfg['bearing_bound_deg'],0,cfg['bearing_bound_deg']]):
            g=r*np.array([np.cos(theta),np.sin(theta)]);d=g-q
            if np.linalg.norm(d)<=5:continue
            deg=np.degrees(np.arctan2(d[1],d[0]))+e
            A,z=bearing_halfplanes(q,deg,cfg['bearing_bound_deg']);v=clip(poly,A,z)
            assert len(v)>0
            dia=diameter(v);worst=max(worst,dia);radii.append(dia)
        rows.append(dict(forward_m=a,lateral_m=b,guaranteed_omni_reception=bool(safe),move_s=float(np.linalg.norm(q)/5),sampled_worst_diameter_m=worst,sample_count=len(radii)))
    csvsave('second_point_candidates.csv',rows);return rows

def run_case(seed,q,strategy,kind='random',noise='spatial',amplitude=1,cfg=None,label='main'):
    cfg=cfg or CFG;sources=generate(seed,q,kind)
    sim=LocalSimulator(sources,cfg,seed,noise,amplitude);policy=Policy(sim,cfg,q,strategy)
    start=time.perf_counter();status=policy.run();runtime=time.perf_counter()-start
    validate(sim,policy,sources)
    row=dict(group=label,seed=seed,question=q,strategy=strategy,kind=kind,noise=noise,amplitude_deg=amplitude,n_sources=len(sources),n_cleared=len(sim.removed),clearance_ratio=len(sim.removed)/len(sources),total_virtual_s=sim.time,average_per_source_s=sim.time/len(sources),runtime_s=runtime,measure_count=sum(r['action']=='measure' for r in sim.log),clear_attempts=sum(r['action']=='clear' for r in sim.log),failed_clear_attempts=sum(r['action']=='clear' and r['response']['clear_result']!='success' for r in sim.log),**sim.parts,**status)
    return row,{'parameters':cfg,'sources':sources,'row':row,'actions':sim.log,'certificates':policy.certificates}

def figures(rows,geo):
    fontpath='C:/Windows/Fonts/arial.ttf'
    font=lambda n:ImageFont.truetype(fontpath,n)
    im=Image.new('RGB',(1200,620),'white');d=ImageDraw.Draw(im)
    d.text((35,25),'Local synthetic results | 40 paired cases per question',font=font(27),fill='#182738')
    d.text((35,66),'Mean virtual seconds per cleared source (lower is better)',font=font(22),fill='#475569')
    means=[np.mean([r['average_per_source_s'] for r in rows if r['question']==q and r['strategy']==s]) for q in [3,4] for s in ['sweep','triangulate']]
    scale=650/max(means)
    for i,(label,value) in enumerate(zip(['Q3 bearing + optical cover','Q3 two bearings + optical cover','Q4 bearing + optical cover','Q4 two bearings + optical cover'],means)):
        y=145+i*102;d.text((35,y),label,font=font(20),fill='#182738')
        d.rectangle((360,y,360+scale*value,y+48),fill='#3b82f6' if i%2 else '#94a3b8');d.text((370+scale*value,y+10),f'{value:.1f}',font=font(20),fill='#182738')
    d.text((35,575),'Generated from cases.csv. These are NOT official simulator tests.',font=font(20),fill='#475569');im.save(OUT/'comparison.png')
    im=Image.new('RGB',(900,620),'white');d=ImageDraw.Draw(im)
    d.text((35,25),'Q1 counterexample: diameter 40 m, enclosing radius 23.094 m',font=font(23),fill='#182738')
    # Equal geometric scale in x and y.
    scale=9.;offset=np.array([260,460]);project=lambda p:tuple(offset+np.array([p[0],-p[1]])*scale)
    v=np.array(geo['equilateral_vertices']);center=np.array(geo['circle_center'])
    x,y=project(center);r=geo['minimum_circle_radius_m']*scale
    d.ellipse((x-r,y-r,x+r,y+r),outline='#2563eb',width=3)
    d.polygon([project(p) for p in v],outline='#e87924',width=4)
    r=20*scale;d.ellipse((x-r,y-r,x+r,y+r),outline='#9ca3af',width=2)
    d.text((35,560),'Blue: minimum enclosing circle. Gray: radius 20 m at the same center.',font=font(21),fill='#475569');im.save(OUT/'q1_counterexample.png')

def main():
    started=time.perf_counter();geo=geometry_checks();second=second_point_study();rows=[];stress=[]
    with gzip.open(OUT/'local_runs.jsonl.gz','wt',encoding='utf-8') as log:
        for q in [3,4]:
            for i in range(CFG['cases_per_question']):
                for strategy in ['sweep','triangulate']:
                    row,detail=run_case(SEED+i,q,strategy);rows.append(row);log.write(json.dumps(detail)+'\n')
                if i%10==0:print(f'Q{q} paired cases {i+1}/{CFG["cases_per_question"]}',flush=True)
        for q in [3,4]:
            for kind,noise,amp in [('boundary','constant',1),('cluster','smooth',1),('radius_min','spatial',1),('all_directional','constant',-1),('random','zero',0),('random','smooth',1)]:
                for i in range(5):
                    row,detail=run_case(SEED+1000+i,q,'triangulate',kind,noise,amp,label='stress');stress.append(row);log.write(json.dumps(detail)+'\n')
        for q in [3,4]:
            for bound,amp in [(0.505,.5),(1.005,1),(1.505,1.5)]:
                cfg=dict(CFG,bearing_bound_deg=bound)
                for i in range(5):
                    row,detail=run_case(SEED+2000+i,q,'triangulate',amplitude=amp,cfg=cfg,label='sensitivity');row['assumed_bound_deg']=bound;stress.append(row);log.write(json.dumps(detail)+'\n')
    csvsave('cases.csv',rows)
    for r in stress:r.setdefault('assumed_bound_deg',CFG['bearing_bound_deg'])
    csvsave('stress_sensitivity.csv',stress)
    summary=[]
    for q in [3,4]:
        for strategy in ['sweep','triangulate']:
            rs=[r for r in rows if r['question']==q and r['strategy']==strategy];ts=np.array([r['average_per_source_s'] for r in rs])
            summary.append(dict(question=q,strategy=strategy,cases=len(rs),total_sources=sum(r['n_sources'] for r in rs),clearance_ratio=sum(r['n_cleared'] for r in rs)/sum(r['n_sources'] for r in rs),mean_case_average_s=float(ts.mean()),median_case_average_s=float(np.median(ts)),p95_case_average_s=float(np.quantile(ts,.95)),max_total_virtual_s=max(r['total_virtual_s'] for r in rs),max_runtime_s=max(r['runtime_s'] for r in rs),mean_failed_clear_attempts=float(np.mean([r['failed_clear_attempts'] for r in rs]))))
    paired=[];rng=np.random.default_rng(SEED+9000)
    for q in [3,4]:
        a=np.array([r['average_per_source_s'] for r in rows if r['question']==q and r['strategy']=='sweep']);b=np.array([r['average_per_source_s'] for r in rows if r['question']==q and r['strategy']=='triangulate']);delta=a-b
        boot=rng.choice(delta,size=(5000,len(delta)),replace=True).mean(axis=1)
        paired.append(dict(question=q,mean_saved_s=float(delta.mean()),relative_mean_reduction=float(1-b.mean()/a.mean()),bootstrap_95_percentile_ci_s=np.quantile(boot,[.025,.975]).tolist(),improved_cases=int(sum(delta>0))))
    save('summary.json',{'main':summary,'paired':paired,'stress_cases':len(stress),'stress_passed':sum(r['clearance_ratio']==1 for r in stress),'all_assertions_passed':True,'wall_runtime_s':time.perf_counter()-started})
    save('environment.json',{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform(),'seed':SEED,'config':CFG,'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.glob('*.py')}})
    figures(rows,geo);print(json.dumps({'main':summary,'paired':paired,'stress_cases':len(stress)},indent=2))

if __name__=='__main__':main()

"""Independent dense checks and Q2 metrics; geometry evidence, not official tests."""
import csv
import itertools
import json
import math
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'analysis_b'))
from model import survey_points,initial_polygon,bearing_halfplanes,clip,diameter,enclosing_circle
from simulator import LocalSimulator
from run_round1 import write_csv,write_json

OUT=ROOT/'experiments/round1'
CFG=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))

def nearest_route(points):
    remain=[p.copy() for p in points];p=np.zeros(2);path=[p.tolist()];length=0.
    while remain:
        i=min(range(len(remain)),key=lambda i:np.linalg.norm(remain[i]-p))
        q=remain.pop(i);length+=np.linalg.norm(q-p);p=q;path.append(p.tolist())
    return float(length),path

def coverage():
    # Cartesian mesh plus exact Voronoi extrema and dense disk boundary.
    axis=np.arange(-1800,1800.01,5);x,y=np.meshgrid(axis,axis)
    samples=np.column_stack([x.ravel(),y.ravel()]);samples=samples[np.linalg.norm(samples,axis=1)<=1800+1e-8]
    angles=np.linspace(0,2*np.pi,14401);boundary=1800*np.column_stack([np.cos(angles),np.sin(angles)])
    samples=np.vstack([samples,boundary]);rows=[];geometries={}
    for layout in ['grid','hexagon']:
        points=np.array(survey_points(3,dict(CFG,q3_survey_layout=layout)));d=[]
        for chunk in np.array_split(samples,100):d.extend(np.linalg.norm(chunk[:,None]-points[None,:],axis=2).min(axis=1))
        d=np.array(d);i=int(d.argmax());length,path=nearest_route(points)
        rows.append(dict(question=3,layout=layout,stations=len(points),sample_count=len(samples),sampled_max_nearest_distance_m=float(d[i]),
                         worst_x=float(samples[i,0]),worst_y=float(samples[i,1]),analytic_max_distance_m=1000/math.sqrt(2) if layout=='grid' else 900.,
                         survey_only_nearest_neighbor_path_m=length,full_20_channel_measure_count=20*len(points),
                         no_source_survey_only_time_s=length/5+119*len(points)))
        geometries[layout]=dict(points=points.tolist(),survey_only_path=path)
    # Q4: all vertices of the containing square are within 600 sqrt(2).
    # Numerical independent angular-gap criterion using *all* stations <=1000m.
    pts=np.array(survey_points(4,CFG));axis=np.arange(-1800,1800.01,20)
    x,y=np.meshgrid(axis,axis);g=np.column_stack([x.ravel(),y.ravel()]);g=g[np.linalg.norm(g,axis=1)<=1800+1e-8]
    g=np.vstack([g,boundary]);maxgap=0.;worst=None;failures=0
    for p in g:
        delta=pts-p;dist=np.linalg.norm(delta,axis=1)
        if dist.min()<1e-8:continue
        a=np.sort(np.arctan2(delta[dist<=1000+1e-8,1],delta[dist<=1000+1e-8,0]))
        gap=float(np.max(np.diff(np.r_[a,a[0]+2*np.pi]))) if len(a) else 2*np.pi
        if gap>maxgap:maxgap=gap;worst=p.tolist()
        if gap>np.pi+1e-8:failures+=1
    q4=dict(points=pts.tolist(),sample_count=len(g),max_angular_gap_deg=math.degrees(maxgap),worst_point=worst,failures=failures,
            four_vertex_distance_bound_m=600*math.sqrt(2))
    assert failures==0
    # Seven stations do NOT direction-cover: all lie inward of this source.
    sim=LocalSimulator([dict(channel=1,position=[1800,0],radius_m=1000,orientation_deg=0)],CFG,noise='zero')
    counter=[sim.measure(p,1)['measure_result'] for p in survey_points(3,dict(CFG,q3_survey_layout='hexagon'))]
    assert all(r=='no_signal' for r in counter)
    write_csv(OUT/'coverage.csv',rows)
    write_json(OUT/'coverage_geometry.json',dict(q3=geometries,q4=q4,q4_reject_q3_hexagon_counterexample=dict(source=[1800,0],orientation_deg=0,results=counter)))
    print('Coverage',rows,'Q4 failures',failures,flush=True)

def q2():
    eps=math.radians(CFG['bearing_bound_deg']);poly=initial_polygon(np.zeros(2),0,CFG);rows=[];details=[]
    for a,b in itertools.product([250,500,650,750],[100,250,450]):
        q=np.array([a,b]);safe=q@q<=1000**2 and q@q<=2000*(a*math.cos(eps)-abs(b)*math.sin(eps))
        areas=[];dias=[];rads=[];crossings=[];visible=[]
        for r,theta,e in itertools.product(np.linspace(5.1,1500,21),[-eps,0,eps],[-CFG['bearing_bound_deg'],0,CFG['bearing_bound_deg']]):
            g=r*np.array([math.cos(theta),math.sin(theta)]);delta=g-q;distance=np.linalg.norm(delta)
            visible.append(distance<=max(1000,r)+1e-8)
            if distance<=5:continue
            deg=math.degrees(math.atan2(delta[1],delta[0]))+e;A,z=bearing_halfplanes(q,deg,CFG['bearing_bound_deg'])
            v=clip(poly,A,z);center,rad=enclosing_circle(v);dia=diameter(v)
            area=abs(np.dot(v[:,0],np.roll(v[:,1],-1))-np.dot(v[:,1],np.roll(v[:,0],-1)))/2
            sine=abs(g[0]*delta[1]-g[1]*delta[0])/(r*distance);angle=math.degrees(math.asin(min(1.,sine)))
            areas.append(area);dias.append(dia);rads.append(rad);crossings.append(angle)
            details.append(dict(forward_m=a,lateral_m=b,source_range_m=r,first_error_deg=math.degrees(theta),second_error_deg=e,
                                area_m2=area,diameter_m=dia,mec_radius_m=rad,acute_crossing_angle_deg=angle,second_visible=bool(visible[-1])))
        rows.append(dict(forward_m=a,lateral_m=b,guaranteed_omni_reception=bool(safe),sampled_reception_fraction=float(np.mean(visible)),
                         movement_m=float(np.linalg.norm(q)),movement_s=float(np.linalg.norm(q)/5),sample_count=len(dias),
                         sampled_mean_area_m2=float(np.mean(areas)),sampled_max_area_m2=float(max(areas)),
                         sampled_mean_diameter_m=float(np.mean(dias)),sampled_max_diameter_m=float(max(dias)),
                         sampled_mean_mec_radius_m=float(np.mean(rads)),sampled_max_mec_radius_m=float(max(rads)),
                         sampled_min_acute_crossing_deg=float(min(crossings))))
    write_csv(OUT/'q2_candidates.csv',rows);write_csv(OUT/'q2_scenarios.csv',details)
    write_json(OUT/'q2_region.json',dict(first_station=[0,0],bearing_deg=0,epsilon_deg=CFG['bearing_bound_deg'],
               constraints=['a^2+b^2 <= 1000^2','a^2+b^2 <= 2000*(a*cos(eps)-abs(b)*sin(eps))'],
               note='Sufficient reception region; scenario extrema are not continuous minimax optima. No probability model assumed.'))
    print('Q2',len(rows),'candidates,',len(details),'scenarios',flush=True)

if __name__=='__main__':coverage();q2()

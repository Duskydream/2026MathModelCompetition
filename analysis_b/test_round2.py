"""Independent geometry regressions for Experiment 2; no official connections."""
import importlib.util
import json
import math
import unittest
from pathlib import Path
import numpy as np
from model import survey_points
from simulator import LocalSimulator

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'analysis_b'/'config.json').read_text(encoding='utf-8'))

def containing_vertices(points,spacing):
    """Invert the infinite lattice and pick a cell by barycentric coordinates."""
    height=spacing*math.sqrt(3)/2
    shifted=np.asarray(points)+[spacing/2,height/3]
    v=shifted[:,1]/height
    u=shifted[:,0]/spacing-v/2
    i=np.floor(u);j=np.floor(v)
    upper=((u-i)+(v-j)>1)
    ids=np.stack([np.stack([i,j],axis=1),
                  np.stack([i+1,j],axis=1),
                  np.stack([i,j+1],axis=1)],axis=1)
    ids[upper,0,0]+=1;ids[upper,0,1]+=1
    vertices=np.empty_like(ids)
    vertices[:,:,0]=spacing*(ids[:,:,0]+ids[:,:,1]/2)-spacing/2
    vertices[:,:,1]=height*ids[:,:,1]-height/3
    return vertices

def geometry_validation():
    spacing=CFG['q4_triangle_spacing_m'];radius=CFG['region_radius_m']
    stations=np.array(survey_points(4,CFG))
    axis=np.arange(-radius,radius+0.01,20.)
    xy=np.array(np.meshgrid(axis,axis)).reshape(2,-1).T
    xy=xy[np.sum(xy*xy,axis=1)<=radius**2]
    angles=np.arange(7200)*2*math.pi/7200
    circle=np.column_stack([np.cos(angles),np.sin(angles)])
    points=np.vstack([xy,radius*circle,(radius-1e-7)*circle,
                      stations[np.linalg.norm(stations,axis=1)<=radius]])
    # Explicit lattice edge/junction and reception-circle thresholds.
    edge=[]
    for a in stations:
        for b in stations:
            if abs(np.linalg.norm(a-b)-spacing)<1e-6:
                edge.extend(a+t*(b-a) for t in [0.,1e-10,0.25,0.5,0.75,1-1e-10,1.])
        edge.extend(a+CFG['receiver_radius_min_m']*circle[::30])
    edge=np.array(edge);edge=edge[np.linalg.norm(edge,axis=1)<=radius]
    points=np.vstack([points,edge])
    tri=containing_vertices(points,spacing)
    # Independent membership check, rather than reusing the intersection routine.
    missing=0
    for start in range(0,len(tri),1000):
        delta=tri[start:start+1000,:,None,:]-stations[None,None,:,:]
        nearest=np.linalg.norm(delta,axis=-1).min(axis=-1)
        missing+=int(np.count_nonzero(nearest>1e-6))
    max_distance=float(np.linalg.norm(tri-points[:,None,:],axis=-1).max())
    # Convex hull membership from nonnegative barycentric coordinates.
    worst_bary=0.
    for start in range(0,len(tri),1000):
        t=tri[start:start+1000];p=points[start:start+1000]
        matrix=np.stack([t[:,1]-t[:,0],t[:,2]-t[:,0]],axis=-1)
        weights=np.linalg.solve(matrix,(p-t[:,0])[...,None])[...,0]
        bary=np.column_stack([1-weights.sum(axis=1),weights])
        worst_bary=min(worst_bary,float(bary.min()))
    max_gap=0.;violations=0;coincident=0
    for start in range(0,len(points),1000):
        delta=stations[None,:,:]-points[start:start+1000,None,:]
        dist=np.linalg.norm(delta,axis=-1)
        for d,dd in zip(delta,dist):
            if dd.min()<1e-7:
                coincident+=1;continue
            visible=d[dd<=CFG['receiver_radius_min_m']+1e-7]
            a=np.sort(np.arctan2(visible[:,1],visible[:,0]))
            gap=float(np.degrees(np.diff(np.r_[a,a[0]+2*math.pi])).max())
            max_gap=max(max_gap,gap);violations+=int(gap>180+1e-7)
    assert missing==0 and max_distance<=spacing+1e-6 and worst_bary>=-1e-8
    assert violations==0 and len(stations)==27
    return dict(stations=len(stations),checked_positions=len(points),missing_cell_vertices=missing,
                max_containing_vertex_distance_m=max_distance,min_barycentric_weight=worst_bary,
                max_direction_gap_deg=max_gap,direction_violations=violations,
                coincident_stations_handled_as_near=coincident,
                stations_xy=stations.tolist())

class TriangleCoverageTests(unittest.TestCase):
    def test_geometry_boundary_edges_and_directions(self):
        result=geometry_validation()
        self.assertLessEqual(result['max_direction_gap_deg'],180+1e-7)

    def test_q3_and_legacy_q4_are_exactly_preserved(self):
        spec=importlib.util.spec_from_file_location('frozen_model',ROOT/'experiments/round2/baseline/model.py')
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for layout in ['grid','hexagon']:
            cfg=dict(CFG,q3_survey_layout=layout)
            cfg.pop('q3_ring_radius_m',None)
            self.assertTrue(np.array_equal(survey_points(3,cfg),old.survey_points(3,cfg)))
        self.assertTrue(np.array_equal(survey_points(4,dict(CFG,q4_survey_layout='grid')),
                                       old.survey_points(4,CFG)))

    def test_spacing_and_layout_validation(self):
        for key in ['region_radius_m','receiver_radius_min_m','q4_triangle_spacing_m']:
            for value in [0,-1,float('nan'),float('inf')]:
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    survey_points(4,dict(CFG,**{key:value}))
        for spacing in [1000,1001]:
            with self.assertRaises(ValueError):
                survey_points(4,dict(CFG,q4_triangle_spacing_m=spacing))
        with self.assertRaises(ValueError):survey_points(4,dict(CFG,q4_survey_layout='bad'))

    def test_closed_disk_tangent_triangle_is_kept(self):
        s=950.;h=s*math.sqrt(3)/2
        # Disk touches the right edge of the cell whose centroid is the origin.
        tangent=s*math.sqrt(3)/6
        for radius in [tangent,tangent+1e-7]:
            pts=np.array(survey_points(4,dict(CFG,region_radius_m=radius)))
            outside=np.array([s,h*2/3])
            self.assertLess(np.linalg.norm(pts-outside,axis=1).min(),1e-6)

    def test_actual_sensor_detects_every_boundary_orientation(self):
        stations=survey_points(4,CFG)
        for angle in range(0,360,10):
            source=CFG['region_radius_m']*np.array([math.cos(math.radians(angle)),math.sin(math.radians(angle))])
            for orient in range(0,360,10):
                sim=LocalSimulator([dict(channel=1,position=source.tolist(),radius_m=1000,orientation_deg=orient)],CFG,noise='zero')
                self.assertTrue(any(sim.measure(p,1)['measure_result']!='no_signal' for p in stations))

if __name__=='__main__':unittest.main(verbosity=2)

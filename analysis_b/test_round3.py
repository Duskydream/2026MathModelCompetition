"""Q3 coverage and set-containment tests; all simulation is local."""
import json,math,unittest
from pathlib import Path
import numpy as np
from model import survey_points
from q3_policy import outside_disk_hull
from optimized import OptimizedPolicy
from simulator import LocalSimulator
CFG=json.loads((Path(__file__).parent/'config.json').read_text())

def contained(poly,points,tolerance=1e-6):
    edge=np.roll(poly,-1,axis=0)-poly
    delta=points[:,None,:]-poly
    cross=edge[None,:,0]*delta[:,:,1]-edge[None,:,1]*delta[:,:,0]
    return np.all(cross>=-tolerance,axis=1)

def coverage_validation():
    stations=np.array(survey_points(3,CFG));R=CFG['region_radius_m'];ring=CFG['q3_ring_radius_m']
    analytic=max(ring/math.sqrt(3),math.sqrt(R*R+ring*ring-math.sqrt(3)*R*ring))
    angles=np.arange(7200)*2*math.pi/7200
    positions=np.vstack([r*np.column_stack([np.cos(angles),np.sin(angles)]) for r in [0,ring/math.sqrt(3),1000,R-1e-7,R]])
    grid=np.arange(-R,R+1,20)
    xy=np.array(np.meshgrid(grid,grid)).reshape(2,-1).T
    positions=np.vstack([positions,xy[np.sum(xy*xy,axis=1)<=R*R]])
    worst=float(np.linalg.norm(positions[:,None,:]-stations[None,:,:],axis=-1).min(axis=1).max())
    assert worst<=analytic+1e-6 and analytic<CFG['receiver_radius_min_m']
    return dict(stations=7,ring_m=ring,checked_positions=len(positions),analytic_worst_distance_m=analytic,
                sampled_worst_distance_m=worst,margin_m=CFG['receiver_radius_min_m']-analytic)

class Q3Tests(unittest.TestCase):
    def test_continuous_coverage_bound_and_boundary(self):
        self.assertLess(coverage_validation()['analytic_worst_distance_m'],1000)
    def test_unsafe_ring_rejected(self):
        for r in [1100,0,-1,float('nan'),float('inf'),2000]:
            with self.subTest(radius=r),self.assertRaises(ValueError):
                survey_points(3,dict(CFG,q3_ring_radius_m=r))
    def test_disk_subtraction_never_drops_feasible_points(self):
        rng=np.random.default_rng(310911)
        for _ in range(50):
            width,height=rng.uniform(10,2000,size=2)
            polygon=np.array([[-width,-height],[width,-height],[width,height],[-width,height]])
            center=rng.uniform(-2000,2000,size=2);radius=float(rng.uniform(1,2200))
            points=rng.uniform([-width,-height],[width,height],size=(3000,2))
            points=points[np.linalg.norm(points-center,axis=1)>=radius+1e-5]
            result=outside_disk_hull(polygon,center,radius)
            self.assertTrue(contained(result,points).all())
    def test_repeated_constraint_retains_circle_edge_intersections(self):
        polygon=np.array([[-1485.097488229121,212.55082379014857],
                          [-1491.6387296450423,160.33185105037177],
                          [-816.5512073560664,87.76868282574577],
                          [-808.8053095890493,115.75821533709036]])
        station=np.array([150.994762008344,-164.92598899519612])
        truth=np.array([[-1216.6828419871363,136.555415026205]])
        for _ in range(100):
            polygon=outside_disk_hull(polygon,station,1000-1e-4)
            self.assertTrue(contained(polygon,truth).all())

    def test_disk_split_tangency_and_degeneracy(self):
        box=np.array([[-2.,-1.],[2.,-1.],[2.,1.],[-2.,1.]])
        for center,radius in [(np.zeros(2),1.5),(np.array([3.,0.]),1.),(np.zeros(2),10.)]:
            result=outside_disk_hull(box,center,radius)
            for p in box:
                if np.linalg.norm(p-center)>=radius:
                    self.assertTrue(contained(result,p[None,:]).all())
        segment=np.array([[0.,0.],[2.,0.]])
        self.assertTrue(np.array_equal(outside_disk_hull(segment,np.zeros(2),1.),segment))
    def test_q4_cannot_use_omni_no_signal_constraint(self):
        sim=LocalSimulator([],CFG)
        self.assertIsNone(OptimizedPolicy(sim,CFG,4).q3_planner)
        self.assertIsNotNone(OptimizedPolicy(sim,CFG,3).q3_planner)
        self.assertIsNone(OptimizedPolicy(sim,dict(CFG,q3_policy='legacy'),3).q3_planner)
    def test_outward_boundary_source_remains_feasible(self):
        for a in range(0,360,30):
            rad=math.radians(a);source=1800*np.array([math.cos(rad),math.sin(rad)])
            for error in [-1,1]:
                sim=LocalSimulator([dict(channel=1,position=source.tolist(),radius_m=1000,orientation_deg=None)],CFG,noise='constant',amplitude=error)
                policy=OptimizedPolicy(sim,CFG,3)
                policy.measure(np.zeros(2),1)
                for station in survey_points(3,CFG)[1:]:
                    r=policy.measure(station,1)
                    if r['measure_result']!='no_signal':
                        policy.make_track(1,station,r)
                        self.assertTrue(contained(policy.tracks[1]['poly'],source[None,:]).all())
                        break
                else:self.fail('Uncovered boundary source')

if __name__=='__main__':unittest.main(verbosity=2)

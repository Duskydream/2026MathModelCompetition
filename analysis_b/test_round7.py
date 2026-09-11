"""Continuous optical cover checks and counterexamples to RF shortcuts."""
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path
import numpy as np
from model import clip,direction,optical_cells
from optimized import OptimizedPolicy
from q4_optical import strip_cover,clearing_route,route_seconds
from q4_policy import ring_stations
from simulator import LocalSimulator

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))


class Round7Tests(unittest.TestCase):
    def test_strip_rectangles_contain_every_clipped_slab(self):
        rng=np.random.default_rng(2026091207)
        for angle in [0,37,149,270]:
            origin=np.array([17.,-39.]);u=direction(angle);basis=np.stack([u,[-u[1],u[0]]],axis=1)
            for _ in range(10):
                length=float(rng.uniform(25,1500));width=float(rng.uniform(.01,60))
                local=np.array([[0.,0.],[length,-width],[length,width]])
                world=origin+local@basis.T
                columns,rectangles=strip_cover(world,origin,angle,30.,19.9)
                reconstructed=[]
                for rect in rectangles:
                    c=np.array(rect['center']);corners=np.array(rect['corners'])
                    self.assertLessEqual(np.linalg.norm(corners-c,axis=1).max(),19.9+1e-7)
                    reconstructed.append((corners-origin)@basis)
                cuts=sorted({round(float(x),8) for r in reconstructed for x in r[:,0]})
                self.assertAlmostEqual(cuts[0],0,places=7)
                self.assertAlmostEqual(cuts[-1],length,places=7)
                for left,right in zip(cuts[:-1],cuts[1:]):
                    slab=clip(local,[[1,0],[-1,0]],[right,-left])
                    matching=[r for r in reconstructed if abs(r[0,0]-left)<1e-7 and abs(r[1,0]-right)<1e-7]
                    intervals=sorted((r[:,1].min(),r[:,1].max()) for r in matching)
                    self.assertTrue(intervals)
                    self.assertLessEqual(intervals[0][0],slab[:,1].min()+1e-6)
                    self.assertGreaterEqual(intervals[-1][1],slab[:,1].max()-1e-6)
                    for a,b in zip(intervals[:-1],intervals[1:]):self.assertGreaterEqual(a[1]+1e-7,b[0])

    def test_selected_complete_scan_cost_never_exceeds_old_grid(self):
        for poly in [np.array([[0.,0.],[1500.,-26.],[1500.,26.]]),
                     np.array([[0.,0.],[0.,0.],[0.,0.]]),
                     np.array([[0.,0.],[800.,0.]]),
                     np.array([[0.,-70.],[100.,-70.],[100.,70.],[0.,70.]])]:
            for start in [np.array([-100.,50.]),np.array([1500.,50.])]:
                old=optical_cells(poly,np.zeros(2),0,25)
                if np.linalg.norm(old[-1]-start)<np.linalg.norm(old[0]-start):old.reverse()
                new,_=clearing_route(poly,np.zeros(2),0,start,CFG)
                self.assertLessEqual(route_seconds(new,start,CFG),route_seconds(old,start,CFG)+1e-6)

    def test_bearing_error_can_lose_signal_800m_before_source(self):
        orientation=np.degrees(np.arctan2(-1.,-.001))%360
        src=[dict(channel=1,position=[1000.,0.],radius_m=1000.,orientation_deg=orientation)]
        sim=LocalSimulator(src,CFG,noise='constant',amplitude=1.)
        result=sim.measure(np.zeros(2),1)
        point=200*direction(result['svd_deg'])
        self.assertEqual(sim.measure(point,1)['measure_result'],'no_signal')
        self.assertGreater(np.linalg.norm(point-[1000.,0.]),800)

    def test_each_outer_station_has_exclusive_directional_witness(self):
        stations=ring_stations(CFG)
        for index in range(13,25):
            unit=stations[index]/np.linalg.norm(stations[index]);point=1800*unit
            src=[dict(channel=1,position=point.tolist(),radius_m=1000.,orientation_deg=np.degrees(np.arctan2(unit[1],unit[0]))%360)]
            sim=LocalSimulator(src,CFG,noise='zero')
            visible=[i for i,p in enumerate(stations) if sim.measure(p,1)['measure_result']!='no_signal']
            self.assertEqual(visible,[index])

    def test_near_cleared_before_next_channel_measurement(self):
        src=[dict(channel=7,position=[0.,0.],radius_m=1000.,orientation_deg=None)]
        sim=LocalSimulator(src,CFG,noise='zero');policy=OptimizedPolicy(sim,CFG,4)
        policy.run()
        index=next(i for i,a in enumerate(sim.log) if a['action']=='measure' and a['response']['measure_result']=='near')
        self.assertEqual(sim.log[index+1]['action'],'clear')
        self.assertEqual(sim.log[index+1]['channel'],7)
        self.assertEqual(sum(a['action']=='clear' for a in sim.log),1)


if __name__=='__main__':unittest.main(verbosity=2)

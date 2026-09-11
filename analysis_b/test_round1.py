"""Geometry/coverage regressions. No official simulator connections."""
import json
import math
import unittest
from pathlib import Path
import numpy as np
from model import (bearing_halfplanes, polygon_from_halfplanes, enclosing_circle,
                   survey_points, initial_polygon, clip, optical_cells)
from simulator import LocalSimulator

CFG=json.loads((Path(__file__).parent/'config.json').read_text(encoding='utf-8'))

class GeometryCoverageTests(unittest.TestCase):
    def test_bearing_wrap_and_backward_ray(self):
        for angle in [0,0.2,359.8,90,180,270]:
            A,b=bearing_halfplanes([23,-41],angle,1)
            for error in [-1,-0.99,0,0.99,1]:
                t=math.radians(angle+error)
                p=np.array([23,-41])+1000*np.array([math.cos(t),math.sin(t)])
                self.assertTrue(np.all(A@p<=b+1e-8))
            t=math.radians(angle+180)
            p=np.array([23,-41])+1000*np.array([math.cos(t),math.sin(t)])
            self.assertFalse(np.all(A@p<=b+1e-8))

    def test_degenerate_regions_and_diameter_counterexample(self):
        A,b=bearing_halfplanes([0,0],0,1)
        self.assertEqual(polygon_from_halfplanes(A,b)['status'],'unbounded')
        self.assertEqual(polygon_from_halfplanes([[1,0],[-1,0]],[0,-1])['status'],'empty')
        box=[[1,0],[-1,0],[0,1],[0,-1]]
        self.assertEqual(polygon_from_halfplanes(box,[0,0,0,0])['diameter'],0)
        self.assertAlmostEqual(polygon_from_halfplanes(box,[1,0,0,0])['diameter'],1)
        tri=np.array([[0.,0.],[40.,0.],[20.,20*math.sqrt(3)]])
        aa=[];bb=[]
        for p,q in zip(tri,np.roll(tri,-1,axis=0)):
            u=(q-p)/40;s=p-1100*u
            A,b=bearing_halfplanes(s,math.degrees(math.atan2(u[1],u[0]))+1,1)
            aa.extend(A);bb.extend(b)
        region=polygon_from_halfplanes(aa,bb)
        self.assertAlmostEqual(region['diameter'],40)
        self.assertAlmostEqual(enclosing_circle(region['vertices'])[1],40/math.sqrt(3))

    def test_hexagon_continuous_bound_extrema(self):
        pts=np.array(survey_points(3,dict(CFG,q3_survey_layout='hexagon',q3_ring_radius_m=1800*math.cos(math.pi/6))))
        self.assertEqual(len(pts),7)
        # Voronoi junctions and boundary bisectors attain the exact bound 900.
        for radius in [900,1800]:
            for k in range(6):
                a=math.radians(30+60*k);p=radius*np.array([math.cos(a),math.sin(a)])
                self.assertAlmostEqual(np.linalg.norm(pts-p,axis=1).min(),900)
        with self.assertRaises(ValueError):
            survey_points(3,dict(CFG,q3_survey_layout='hexagon',region_radius_m=2100))
        self.assertTrue(np.array_equal(survey_points(4,dict(CFG,q3_survey_layout='grid')),
                                       survey_points(4,dict(CFG,q3_survey_layout='hexagon',q3_ring_radius_m=1800*math.cos(math.pi/6)))))

    def test_q4_closed_halfplane_and_optical_backside(self):
        sim=LocalSimulator([dict(channel=1,position=[1800,0],radius_m=1000,orientation_deg=0)],CFG,noise='zero')
        self.assertEqual(sim.measure([1200,0],1)['measure_result'],'no_signal')
        self.assertEqual(sim.measure([1800,600],1)['measure_result'],'direction')
        self.assertEqual(sim.measure([1800,0],1)['measure_result'],'near')
        self.assertEqual(sim.clear([1780,0],1)['clear_result'],'success')
        self.assertEqual(sim.channel,1)

    def test_rounding_region_and_optical_coverage(self):
        for angle in [0,359.995,135]:
            p=np.array([1800.,0.]);poly=initial_polygon(p,angle,CFG)
            cells=np.array(optical_cells(poly,p,angle,25))
            for radius in [5.01,1000,1500]:
                for error in [-1.005,0,1.005]:
                    a=math.radians(angle+error);g=p+radius*np.array([math.cos(a),math.sin(a)])
                    self.assertLessEqual(np.linalg.norm(cells-g,axis=1).min(),20)

if __name__=='__main__':unittest.main()

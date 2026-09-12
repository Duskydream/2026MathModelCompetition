"""Explicit Q4 station lists: coverage guard, certificate agreement and directional witnesses."""
import json
import math
import unittest
from pathlib import Path
import numpy as np
from q4_policy import hull_coverage_slack, ring_stations, survey_stations
from simulator import LocalSimulator

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))


class Round8Tests(unittest.TestCase):
    def test_configured_list_matches_certificate_file(self):
        cert=json.loads((ROOT/'experiments/q4_layout_search/ring22_certificate.json').read_text())
        self.assertTrue(cert['certified'])
        self.assertGreaterEqual(cert['min_slack'],cert['delta'])
        np.testing.assert_allclose(np.asarray(CFG['q4_station_list']),np.asarray(cert['stations']))
        self.assertEqual(len(survey_stations(CFG)),22)

    def test_analytic_rings_and_list_pass_coarse_check(self):
        self.assertGreaterEqual(hull_coverage_slack(ring_stations(CFG),CFG),-1e-6)
        self.assertGreater(hull_coverage_slack(CFG['q4_station_list'],CFG),0)

    def test_uncovered_lists_are_rejected(self):
        stations=list(CFG['q4_station_list'])
        with self.assertRaises(ValueError):survey_stations(dict(CFG,q4_station_list=stations[:-1]))
        with self.assertRaises(ValueError):survey_stations(dict(CFG,q4_station_list=[[0,0],[1,1]]))
        with self.assertRaises(ValueError):survey_stations(dict(CFG,q4_station_list=[[0,0],[1,math.nan],[2,2]]))
        self.assertEqual(len(survey_stations(dict(CFG,q4_station_list=None))),25)

    def test_boundary_sources_facing_outward_are_detected(self):
        """Every boundary source facing away from the center is seen from some station."""
        stations=survey_stations(CFG)
        for deg in range(0,360,3):
            unit=np.array([math.cos(math.radians(deg)),math.sin(math.radians(deg))])
            src=[dict(channel=1,position=(1800*unit).tolist(),radius_m=1000.,orientation_deg=deg)]
            sim=LocalSimulator(src,CFG,noise='zero')
            self.assertTrue(any(sim.measure(p,1)['measure_result']!='no_signal' for p in stations),deg)

    def test_random_interior_orientations_are_detected(self):
        stations=survey_stations(CFG);rng=np.random.default_rng(8)
        for _ in range(300):
            angle=rng.uniform(0,2*math.pi);radius=1800*math.sqrt(rng.random())
            src=[dict(channel=1,position=[radius*math.cos(angle),radius*math.sin(angle)],radius_m=1000.,orientation_deg=float(rng.uniform(0,360)))]
            sim=LocalSimulator(src,CFG,noise='zero')
            self.assertTrue(any(sim.measure(p,1)['measure_result']!='no_signal' for p in stations))


if __name__=='__main__':unittest.main(verbosity=2)

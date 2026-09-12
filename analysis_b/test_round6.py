"""Q4 waiting, selective measurements and refinement failure boundaries."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from model import enclosing_circle
from optimized import OptimizedPolicy
from q4_policy import polygon_distance, survey_stations
from simulator import LocalSimulator, generate

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))


class Round6Tests(unittest.TestCase):
    def policy(self,sources=(),**overrides):
        cfg=dict(CFG,**overrides)
        sim=LocalSimulator(sources,cfg,noise='zero')
        return OptimizedPolicy(sim,cfg,4),sim

    def track(self,policy,poly):
        policy.tracks[1]=dict(origin=np.zeros(2),deg=0.,poly=np.asarray(poly,float),
                             count=1,near=None,extra=0,sample_points=[np.zeros(2)])

    def test_polygon_distance_segments_and_both_windings(self):
        box=np.array([[0.,0.],[3.,0.],[3.,2.],[0.,2.]])
        for poly in (box,box[::-1]):
            self.assertEqual(polygon_distance(poly,[1,1]),0)
            self.assertAlmostEqual(polygon_distance(poly,[6,6]),5)
        self.assertEqual(polygon_distance([[0,0],[2,0]],[3,0]),1)
        self.assertEqual(polygon_distance([[0,0]],[3,4]),5)
        with self.assertRaises(ValueError):polygon_distance([],np.zeros(2))

    def test_polygon_gate_keeps_near_edge_of_long_region(self):
        policy,_=self.policy(q4_help_distance='polygon')
        self.track(policy,[[900,-10],[1500,-10],[1500,10],[900,10]])
        self.assertTrue(policy.planner.close_enough(np.zeros(2),1))
        self.assertGreater(np.linalg.norm(enclosing_circle(policy.tracks[1]['poly'])[0]),950)

    def test_unseen_channels_are_never_skipped(self):
        policy,sim=self.policy()
        status=policy.run()
        count=len(survey_stations(CFG))
        self.assertEqual(status['visited_survey_points'],count)
        self.assertEqual(status['termination'],'full_coverage')
        self.assertEqual(len(sim.log),count*20)
        for offset in range(0,len(sim.log),20):
            self.assertEqual({a['channel'] for a in sim.log[offset:offset+20]},set(range(1,21)))

    def test_waiting_ends_when_stations_exhausted_or_target_stale(self):
        policy,_=self.policy()
        self.track(policy,[[400,-10],[1000,-10],[1000,10],[400,10]])
        helpers=[np.array([700.,400.])]
        self.assertTrue(np.isinf(policy.planner.target_cost(1,helpers)))
        self.assertTrue(np.isfinite(policy.planner.target_cost(1,[])))
        policy.pos=np.array([2000.,0.])
        self.assertTrue(np.isfinite(policy.planner.target_cost(1,helpers)))

    def test_ready_target_not_deferred(self):
        policy,_=self.policy()
        self.track(policy,[[400,-10],[420,-10],[420,10],[400,10]])
        self.assertTrue(np.isfinite(policy.planner.target_cost(1,[np.array([410.,0.])])))
        self.assertFalse(policy.planner.useful(np.array([410.,0.]),1))

    def test_outer_ring_detection_is_not_deferred_to_backside_stations(self):
        policy,_=self.policy(q4_wait_mode='inner')
        self.track(policy,[[1100,-20],[1800,-20],[1800,20],[1100,20]])
        origin=np.array([1863.,0.])
        policy.tracks[1]['origin']=origin
        policy.pos=origin.copy()
        self.assertTrue(np.isfinite(policy.planner.target_cost(1,[np.array([999.,0.])])))

    def test_center_silence_preserves_region_and_optical_fallback(self):
        sources=[dict(channel=1,position=[200.,0.],radius_m=1000.,orientation_deg=180.)]
        policy,sim=self.policy(sources)
        response=policy.measure(np.zeros(2),1)
        policy.make_track(1,np.zeros(2),response)
        self.track(policy,[[190,-30],[290,-30],[290,30],[190,30]])
        previous=policy.tracks[1]['poly'].copy()
        policy.planner.refine(1)
        self.assertEqual(sim.log[-1]['response']['measure_result'],'no_signal')
        np.testing.assert_allclose(policy.tracks[1]['poly'],previous)
        policy.finish(1)
        self.assertEqual(policy.cleared,{1})

    def test_uninformative_refinement_limited_to_two_measurements(self):
        policy,_=self.policy()
        self.track(policy,[[190,-30],[290,-30],[290,30],[190,30]])
        with patch.object(policy,'measure',return_value={'measure_result':'direction','svd_deg':0.}) as measure:
            with patch.object(policy,'update'):
                policy.planner.refine(1)
        self.assertEqual(measure.call_count,2)

    def test_invalid_parameters(self):
        for params in [dict(q4_wait_stale_m=0),dict(q4_refine_max_m=float('nan')),
                       dict(q4_remeasure_min_sine=1.1),dict(q4_help_distance='unknown'),
                       dict(q4_station_help_m=1000),dict(q4_wait_for_survey='false')]:
            with self.subTest(params=params),self.assertRaises(ValueError):self.policy(**params)

    def test_disabled_features_replay_original_planner(self):
        path=ROOT/'experiments/round6/baseline/q4_policy.py'
        spec=importlib.util.spec_from_file_location('round6_test_baseline',path)
        baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
        # The frozen baseline only knows the analytic 25-station rings.
        cfg=dict(CFG,q4_station_list=None,q4_selective_remeasure=False,q4_wait_for_survey=False,
                 q4_refine_max_m=0,q4_shared_scan=True,q4_strip_cover=False,
                 q4_immediate_near=False,q4_scan_cost_gate=False)
        for seed in [2026100100,2026100101]:
            sources=generate(seed,4)
            actual=LocalSimulator(sources,cfg,seed);expected=LocalSimulator(sources,cfg,seed)
            candidate=OptimizedPolicy(actual,cfg,4);original=OptimizedPolicy(expected,cfg,4)
            original.planner=baseline.Q4Planner(original)
            candidate.run();original.run()
            self.assertEqual(actual.log,expected.log)
            self.assertEqual(candidate.cleared,{s['channel'] for s in sources})


if __name__=='__main__':unittest.main(verbosity=2)

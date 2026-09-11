"""Continuous coverage, directional silence and production replay checks."""
import gzip
import json
import math
import unittest
from pathlib import Path
import numpy as np
from q4_policy import ring_stations
from optimized import OptimizedPolicy
from simulator import LocalSimulator

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'analysis_b/config.json').read_text())


class Round4Tests(unittest.TestCase):
    def test_continuous_cover(self):
        stations=np.array(ring_stations(CFG))
        self.assertEqual(len(stations),25)
        # Explicit conforming triangles: center fan, then annulus strip.
        triangles=[]
        for k in range(12):
            a=1+k;b=1+(k+1)%12;c=13+k;d=13+(k-1)%12
            triangles.extend([(0,a,b),(a,b,c),(a,c,d)])
        areas=[]
        for ids in triangles:
            t=stations[list(ids)]
            self.assertLess(np.linalg.norm(t[:,None]-t[None,:],axis=2).max(),1000.)
            areas.append(abs(np.linalg.det(np.stack([t[1]-t[0],t[2]-t[0]])))/2)
        outer=np.linalg.norm(stations[13])
        self.assertGreaterEqual(outer*math.cos(math.pi/12),1800.-1e-8)
        self.assertAlmostEqual(sum(areas),6*outer**2*math.sin(math.pi/6),places=6)

    def test_silence_does_not_exclude_nearby_source(self):
        source=dict(channel=1,position=[200.,0.],radius_m=1000.,orientation_deg=180.)
        sim=LocalSimulator([source],CFG,0,'zero')
        policy=OptimizedPolicy(sim,CFG,4)
        r=policy.measure(np.zeros(2),1);policy.make_track(1,np.zeros(2),r)
        previous=policy.tracks[1]['poly'].copy()
        position=np.array([300.,0.]);r=policy.measure(position,1)
        self.assertEqual(r['measure_result'],'no_signal')
        policy.update(1,position,r)
        np.testing.assert_allclose(policy.tracks[1]['poly'],previous,atol=1e-8)

    def test_invalid_geometry_rejected(self):
        with self.assertRaises(ValueError):ring_stations(dict(CFG,receiver_radius_min_m=990))


def replay(question=4):
    from experiments import validate
    path=ROOT/('experiments/round4/ring25_actions.jsonl.gz' if question==4 else 'experiments/round3/actions.jsonl.gz')
    count=0
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for entry in map(json.loads,stream):
            row=entry['row']
            if question==4 and row['variant']!='ring25':continue
            if question==3 and (row['variant']!='candidate' or row['question']!=3):continue
            sim=LocalSimulator(entry['sources'],CFG,row['seed'],row['noise'],row.get('amplitude',1))
            policy=OptimizedPolicy(sim,CFG,question)
            policy.run();validate(sim,policy,entry['sources'])
            # Prototype and integrated implementation must have same behavior.
            assert len(sim.log)==len(entry['actions']), row
            for actual,expected in zip(sim.log,entry['actions']):
                assert actual['action']==expected['action'] and actual['channel']==expected['channel']
                np.testing.assert_allclose(actual['position'],expected['position'],atol=1e-6,rtol=0)
                for key,value in expected['response'].items():
                    if isinstance(value,(int,float)):
                        assert abs(actual['response'][key]-value)<1e-6
                    else:assert actual['response'][key]==value
            count+=1
            if count%20==0:print('production replay',count,flush=True)
    result=dict(cases=count,all_actions_match=True,all_cleared=True)
    name='production_replay.json' if question==4 else 'q3_regression.json'
    (ROOT/'experiments/round4'/name).write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    import sys
    if '--replay' in sys.argv:replay()
    elif '--q3-replay' in sys.argv:replay(3)
    else:unittest.main()

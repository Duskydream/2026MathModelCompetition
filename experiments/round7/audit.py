"""Check the proposed Q4 guarantees and privately summarize practice records."""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis_b'))
from q4_policy import ring_stations
from simulator import LocalSimulator

OUT=ROOT/'.local_archive/q4_round7'
CFG=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))


def guarantees():
    stations=np.asarray(ring_stations(CFG));witnesses=[]
    for index in range(13,25):
        unit=stations[index]/np.linalg.norm(stations[index])
        point=1800*unit
        source=dict(channel=1,position=point.tolist(),radius_m=1000.,
                    orientation_deg=float(np.degrees(np.arctan2(unit[1],unit[0]))%360))
        sim=LocalSimulator([source],CFG,noise='zero')
        visible=[i for i,p in enumerate(stations) if sim.measure(p,1)['measure_result']!='no_signal']
        assert visible==[index],visible
        other=(np.delete(stations,index,axis=0)-point)@unit
        witnesses.append(dict(outer_station=index,source=source,only_visible_station=visible[0],
                              largest_other_forward_projection_m=float(other.max())))
    # Slightly inside the visible half-plane at the first observation, not on its edge.
    orientation=float(np.degrees(np.arctan2(-1.,-.001))%360)
    source=dict(channel=1,position=[1000.,0.],radius_m=1000.,orientation_deg=orientation)
    sim=LocalSimulator([source],CFG,noise='constant',amplitude=1.)
    first=sim.measure([0,0],1)
    point=200*np.array([math.cos(math.radians(first['svd_deg'])),math.sin(math.radians(first['svd_deg']))])
    second=sim.measure(point,1)
    assert first['measure_result']=='direction' and second['measure_result']=='no_signal'
    remaining=float(np.linalg.norm(point-np.array(source['position'])))
    assert remaining>790 and point[0]<source['position'][0]
    return dict(outer_station_counterexamples=witnesses,
                ray_counterexample=dict(source=source,first_response=first,next_point=point.tolist(),
                                        second_response=second,distance_to_source_m=remaining))


def practice():
    groups=defaultdict(list);stations=np.asarray(ring_stations(CFG));private_rows=[]
    for directory in sorted((ROOT/'B题演练程序/practice_logs').glob('q4_*')):
        try:
            cfg=json.loads((directory/'run_config.json').read_text(encoding='utf-8'))
            summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
        except (FileNotFoundError,json.JSONDecodeError):continue
        if summary.get('status')!='completed':continue
        n=summary['cleared_count'];key=cfg.get('code_sha256',{}).get('q4_policy.py','unknown')
        row=dict(run=directory.name,code_sha256=key,cleared=n,seconds_per_cleared=summary['average_per_cleared_s'],
                 parts={k:v/n for k,v in summary['time_components_s'].items()},
                 true_source_count=summary.get('true_source_count'))
        pending={};measured=defaultdict(list);clear_runs=[];clear_distance=0.;clear_count=0
        previous=np.zeros(2);seen_stations=[];detected=set();attempts=hits=0
        for line in (directory/'actions.jsonl').read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['event']=='request':
                payload=event['payload'];pending[payload['request_id']]=(event['path'],payload)
            if event['event']!='response':continue
            response=event['body'];request=pending.get(event['request_id'])
            if not request or not response.get('accepted'):continue
            path,payload=request
            if path not in ('/measure','/clear'):continue
            position=payload.get('position',payload)
            point=np.array([position['x'],position['y']],float) if isinstance(position,dict) else np.asarray(position,float)
            channel=payload.get('channel')
            if path=='/measure':
                if clear_count:clear_runs.append(dict(attempts=clear_count,move_m=clear_distance))
                clear_count=0;clear_distance=0.
                measured[channel].append(point.tolist())
                if channel in detected:
                    attempts+=1;hits+=response['measure_result']!='no_signal'
                if response['measure_result']!='no_signal':detected.add(channel)
                matches=np.flatnonzero(np.linalg.norm(stations-point,axis=1)<1e-5)
                if len(matches) and int(matches[0]) not in seen_stations:seen_stations.append(int(matches[0]))
            else:
                clear_count+=1;clear_distance+=float(np.linalg.norm(point-previous))
            previous=point
        if clear_count:clear_runs.append(dict(attempts=clear_count,move_m=clear_distance))
        row['tracked_measurements']=attempts;row['tracked_no_signal']=attempts-hits
        row['max_clear_streak']=max(clear_runs,key=lambda x:x['attempts']) if clear_runs else None
        row['station_visit_order']=seen_stations
        if all(i in seen_stations for i in range(13,25)):
            row['stations_seen_at_last_outer']=1+max(seen_stations.index(i) for i in range(13,25))
        groups[key].append(row);private_rows.append(row)
    result={}
    for key,rows in groups.items():
        values=np.array([r['seconds_per_cleared'] for r in rows])
        count=sum(r['tracked_measurements'] for r in rows)
        result[key]=dict(cases=len(rows),mean=float(values.mean()),std=float(values.std(ddof=1)) if len(rows)>1 else None,
                         variance=float(values.var(ddof=1)) if len(rows)>1 else None,
                         p95=float(np.percentile(values,95)),maximum=float(values.max()),
                         per_source_parts={k:float(np.mean([r['parts'][k] for r in rows])) for k in rows[0]['parts']},
                         tracked_silent_fraction=sum(r['tracked_no_signal'] for r in rows)/count if count else None,
                         stations_at_last_outer=[r.get('stations_seen_at_last_outer') for r in rows],
                         maximum_clear_attempt_streak=max(r['max_clear_streak']['attempts'] for r in rows if r['max_clear_streak']),
                         true_total_known=all(r['true_source_count'] is not None for r in rows))
    (OUT/'private_practice_rows.json').write_text(json.dumps(private_rows,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    result=dict(guarantees=guarantees(),practice=practice())
    (OUT/'audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

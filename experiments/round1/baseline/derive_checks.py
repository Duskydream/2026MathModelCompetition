"""Additional analytical-bound calculations and distribution/parameter audit."""
from pathlib import Path
import csv,gzip,json,math
import numpy as np
from model import initial_polygon,optical_cells,bearing_halfplanes

BASE=Path(__file__).resolve().parent;OUT=BASE/'results';cfg=json.loads((BASE/'config.json').read_text())
p=initial_polygon(np.zeros(2),0,cfg);cells=optical_cells(p,np.zeros(2),0,cfg['optical_grid_m'])
path=sum(np.linalg.norm(b-a) for a,b in zip(cells,cells[1:]))
rows=list(csv.DictReader((OUT/'cases.csv').open(encoding='utf-8-sig')))
parts=[]
for q in [3,4]:
 for strategy in ['sweep','triangulate']:
  r=[v for v in rows if int(v['question'])==q and v['strategy']==strategy]
  parts.append(dict(question=q,strategy=strategy,components_mean_s_per_source={k:float(np.mean([float(v[k])/int(v['n_sources']) for v in r])) for k in ['move','switch','measure','optical','laser']},max_actions=max(int(v['measure_count'])+int(v['clear_attempts']) for v in r)))
cases=0;missing=0;bad=0;counts=[]
with gzip.open(OUT/'local_runs.jsonl.gz','rt',encoding='utf-8') as f:
 for line in f:
  run=json.loads(line);sources=run['sources'];counts.append(len(sources));cases+=1
  assert len({s['channel'] for s in sources})==len(sources)
  for s in sources:
   missing+=sum(s[k] is None for k in ['channel','position','radius_m'])
   assert 1<=s['channel']<=20 and np.linalg.norm(s['position'])<=1800+1e-7 and 1000<=s['radius_m']<=1500
   assert s['orientation_deg'] is None or 0<=s['orientation_deg']<360
  assert 10<=len(sources)<=16
# Show why an error exceeding the assumed bound cannot have a guarantee.
g=1500*np.array([math.cos(math.radians(1.5)),math.sin(math.radians(1.5))]);A,b=bearing_halfplanes([0,0],0,1.005)
underbound=float(max(A@g-b));assert underbound>0
report=dict(local_runs_checked=cases,synthetic_required_field_missing=missing,synthetic_constraints='all passed',source_count_min=min(counts),source_count_max=max(counts),optical_cell_circumradius_m=25/math.sqrt(2),full_first_polygon_actual_cells=len(cells),full_first_polygon_actual_snake_path_m=float(path),analytic_max_cells=183,analytic_snake_path_bound_m=6500,analytic_virtual_time_bound_s=49*8800/5+49*120+16*((2*8800+6500)/5+6+183*3+2),default_virtual_limit_s=360000,understated_error_counterexample_halfplane_violation_m=underbound,components=parts)
(OUT/'audit_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

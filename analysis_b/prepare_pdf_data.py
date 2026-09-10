"""Calculate explanatory geometry and extract real logs used in the PDF."""
from pathlib import Path
import gzip,json,hashlib
import numpy as np
from model import direction,initial_polygon,bearing_halfplanes,clip,enclosing_circle,diameter

B=Path(__file__).resolve().parent;O=B/'pdf_work';O.mkdir(exist_ok=True)
cfg=json.loads((B/'config.json').read_text())
p=np.zeros(2);g=np.array([1000.,0.]);theta=.6
q=650*direction(theta)+250*direction(theta+90)
theta2=float(np.degrees(np.arctan2(*(g-q)[::-1]))-.4)%360
poly=initial_polygon(p,theta,cfg);A,b=bearing_halfplanes(q,theta2,cfg['bearing_bound_deg']);inter=clip(poly,A,b);center,radius=enclosing_circle(inter)
data={'example':{'station1':p.tolist(),'station2':q.tolist(),'true_source':g.tolist(),'bearing1':theta,'bearing2':theta2,'first_polygon':poly.tolist(),'intersection':inter.tolist(),'center':center.tolist(),'radius_m':radius,'diameter_m':diameter(inter)},'worst_case':[],'sources_sha256':{}}
f=B/'optimization_results/holdout_logs.jsonl.gz'
with gzip.open(f,'rt',encoding='utf-8') as stream:
 for line in stream:
  r=json.loads(line)
  if r['row']['seed']==20270961 and r['row']['question']==4:
   data['worst_case'].append({'row':r['row'],'sources':r['sources'],'path':[[0,0]]+[x['position'] for x in r['actions']]})
assert len(data['worst_case'])==2
for f in [B/'results/summary.json',B/'results/geometry.json',B/'results/audit_checks.json',B/'optimization_results/development_summary.json',B/'optimization_results/holdout_summary.json',B/'optimization_results/stress_summary.json',B/'optimization_results/holdout_regressions.csv',B/'config.json']:
 data['sources_sha256'][str(f.relative_to(B))]=hashlib.sha256(f.read_bytes()).hexdigest()
(O/'report_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(data['example'],indent=2))

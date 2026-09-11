"""Independent paired holdout for the frozen ring25 mixed prototype."""
import gzip
import hashlib
import json
import time
from pathlib import Path

from explore import Candidate, OptimizedPolicy, LocalSimulator, generate, ROOT
from experiments import validate
import numpy as np

OUT = ROOT/'experiments/round4'


def main():
    cfg = json.loads((ROOT/'analysis_b/config.json').read_text())
    candidate_cfg = dict(cfg, q3_second_forward_m=200, q3_second_lateral_m=100, ring25=True)
    specifications = [(2026095100+i, 'random', 'spatial') for i in range(100)]
    specifications += [(2026096100+100*j+i, kind, noise)
                       for j, (kind, noise) in enumerate([
                           ('boundary', 'constant'), ('radius_min', 'spatial'),
                           ('cluster', 'smooth'), ('all_directional', 'constant')])
                       for i in range(15)]
    specification = dict(config=candidate_cfg, cases=specifications,
                         code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in [Path(__file__),Path(__file__).with_name('explore.py'),
                                                ROOT/'experiments/q4_geometry/search_rings.py']})
    (OUT/'ring25_specification.json').write_text(json.dumps(specification,indent=2))
    rows=[]
    with gzip.open(OUT/'ring25_actions.jsonl.gz','wt',encoding='utf-8') as logs:
        for index,(seed,kind,noise) in enumerate(specifications):
            sources=generate(seed,4,kind)
            for label,cls,local in [('main',OptimizedPolicy,cfg),('ring25',Candidate,candidate_cfg)]:
                sim=LocalSimulator(sources,local,seed,noise)
                policy=cls(sim,local,4,'shared')
                start=time.perf_counter();error='';status={}
                try:
                    status=policy.run()
                    validate(sim,policy,sources)
                except Exception as exc:
                    error=repr(exc)
                row=dict(seed=seed,kind=kind,noise=noise,variant=label,
                         sources=len(sources),cleared=len(sim.removed),error=error,
                         average_s=sim.time/len(sources),virtual_s=sim.time,
                         runtime_s=time.perf_counter()-start,parts=sim.parts,**status)
                rows.append(row)
                logs.write(json.dumps(dict(row=row,sources=sources,actions=sim.log,
                                           certificates=policy.certificates))+'\n')
            if index%20==0:print(index+1,'/',len(specifications),flush=True)
    (OUT/'ring25_rows.json').write_text(json.dumps(rows,indent=2))
    summary={}
    for kind in ['random','boundary','radius_min','cluster','all_directional']:
        summary[kind]={}
        for label in ['main','ring25']:
            subset=[r for r in rows if r['kind']==kind and r['variant']==label]
            times=np.array([r['average_s'] for r in subset])
            summary[kind][label]=dict(cases=len(subset),mean=float(times.mean()),
                p95=float(np.quantile(times,.95)),maximum=float(times.max()),
                below500=int(sum(times<500)),failures=sum(bool(r['error']) for r in subset),
                cleared=sum(r['cleared'] for r in subset),sources=sum(r['sources'] for r in subset))
    (OUT/'ring25_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()

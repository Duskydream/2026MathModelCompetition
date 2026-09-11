"""Frozen paired Q4 evaluation emphasizing variance and tail time."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import platform
import shutil
import sys
import time
from pathlib import Path
import numpy as np
import scipy

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SOURCE=ROOT/'analysis_b'
BASE=HERE/'baseline';OUT=ROOT/'.local_archive/q4_round7'
sys.path.insert(0,str(SOURCE));sys.path.insert(0,str(HERE))
FILES=['model.py','optimized.py','q3_policy.py','q4_policy.py','simulator.py','config.json']
VARIANTS={'baseline':{},'strips':{'q4_immediate_near':False},
          'near_only':{'q4_strip_cover':False},'selected':{},
          'cost_gate':{'q4_scan_cost_gate':True},'wait_once':{'q4_wait_once':True},
          'no_wait':{'q4_wait_for_survey':False},'no_refine':{'q4_refine_max_m':0},
          'refine100':{'q4_refine_max_m':100},'refine75':{'q4_refine_max_m':75}}


def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def case_list(suite):
    starts={'smoke':2026110000,'dev':2026111000,'holdout':2026114000,'sensitivity':2026118000}
    counts={'smoke':[3,2,2,2,2,2],'dev':[60,20,20,20,20,20],
            'holdout':[200,50,50,50,50,50],'sensitivity':[30,10,10,10,10,10]}[suite]
    return [(starts[suite]+i*500+j,kind) for i,(kind,n) in enumerate(zip(
        ['random','boundary','radius_min','all_directional','cluster','random_directional'],counts)) for j in range(n)]


def summary(rows):
    output={}
    for kind in sorted({r['kind'] for r in rows}):
        selected=[r for r in rows if r['kind']==kind];output[kind]={}
        baseline={r['seed']:r for r in selected if r['variant']=='baseline'}
        for variant in sorted({r['variant'] for r in selected}):
            rs=[r for r in selected if r['variant']==variant];v=np.array([r['avg'] for r in rs])
            entry=dict(cases=len(rs),mean=float(v.mean()),std=float(v.std(ddof=1)),variance=float(v.var(ddof=1)),
                       p95=float(np.percentile(v,95)),tail_mean=float(np.sort(v)[-max(1,int(np.ceil(.1*len(v)))):].mean()),
                       maximum=float(v.max()),sources=sum(r['sources'] for r in rs),cleared=sum(r['cleared'] for r in rs),
                       parts={k:float(np.mean([r['parts'][k]/r['sources'] for r in rs])) for k in rs[0]['parts']},
                       failed_per_source=float(np.mean([r['fails']/r['sources'] for r in rs])))
            if baseline and variant!='baseline':
                dif=np.array([r['avg']-baseline[r['seed']]['avg'] for r in rs])
                rng=np.random.default_rng(2026091207)
                boots=np.concatenate([rng.choice(dif,(100,len(dif))).mean(axis=1) for _ in range(100)])
                entry['paired']=dict(delta=float(dif.mean()),ci95=np.percentile(boots,[2.5,97.5]).tolist(),
                                      faster=int(sum(dif<-1e-7)),slower=int(sum(dif>1e-7)),
                                      worst_delta=float(dif.max()),worst_seed=rs[int(dif.argmax())]['seed'])
            output[kind][variant]=entry
    return output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--suite',choices=['smoke','dev','holdout','sensitivity'],default='dev')
    parser.add_argument('--variants',nargs='+',choices=list(VARIANTS),default=['baseline','selected'])
    parser.add_argument('--label');parser.add_argument('--noise',default='spatial',choices=['spatial','constant','smooth'])
    parser.add_argument('--amplitude',type=float,default=1.)
    args=parser.parse_args()
    if args.freeze:
        BASE.mkdir(parents=True,exist_ok=False)
        for name in FILES:shutil.copyfile(SOURCE/name,BASE/name)
        save(BASE/'manifest.json',{name:sha(BASE/name) for name in FILES});return
    for name,value in json.loads((BASE/'manifest.json').read_text()).items():assert sha(BASE/name)==value,name
    from optimized import OptimizedPolicy
    from simulator import LocalSimulator,generate
    from candidate import Candidate,BASE as baseline_module
    check_spec=importlib.util.spec_from_file_location('q4_round6_validation',ROOT/'experiments/round6/run.py')
    check=importlib.util.module_from_spec(check_spec);check_spec.loader.exec_module(check)
    cfg=json.loads((BASE/'config.json').read_text());label=args.label or args.suite
    if Path(label).name!=label:raise ValueError('Invalid output label')
    output=OUT/label;output.mkdir(parents=True,exist_ok=False)
    for name in FILES:shutil.copyfile(BASE/name,output/name)
    for path in [Path(__file__),HERE/'candidate.py',SOURCE/'q4_optical.py']:shutil.copyfile(path,output/path.name)
    meta=dict(args=vars(args),python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),
              cfg=cfg,variants={v:VARIANTS[v] for v in args.variants},cases=case_list(args.suite),
              sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()},bootstrap_seed=2026091207)
    save(output/'metadata.json',meta);rows=[]
    with gzip.open(output/'synthetic_actions.jsonl.gz','wt',encoding='utf-8') as stream:
        for index,(seed,kind) in enumerate(case_list(args.suite)):
            sources=generate(seed,4,'random' if kind=='random_directional' else kind)
            if kind=='random_directional':
                rng=np.random.default_rng(seed+100000)
                for source in sources:source['orientation_deg']=float(rng.uniform(0,360))
            for variant in args.variants:
                params=dict(cfg,**VARIANTS[variant]);sim=LocalSimulator(sources,params,seed,args.noise,args.amplitude)
                p=OptimizedPolicy(sim,params,4)
                p.planner=baseline_module.Q4Planner(p) if variant=='baseline' else Candidate(p)
                start=time.perf_counter();status=p.run();runtime=time.perf_counter()-start
                check.validate(sim,p,sources,status)
                row=dict(seed=seed,kind=kind,variant=variant,avg=sim.time/len(sources),sources=len(sources),
                         cleared=len(p.cleared),parts=sim.parts,runtime=runtime,
                         fails=sum(a['action']=='clear' and a['response']['clear_result']!='success' for a in sim.log))
                rows.append(row);stream.write(json.dumps(dict(row=row,sources=sources,actions=sim.log,
                    certificates=p.certificates,status=status))+'\n')
            if (index+1)%10==0:print(label,index+1,'/',len(case_list(args.suite)),flush=True)
    save(output/'results.json',dict(metadata=meta,rows=rows))
    result=summary(rows);save(HERE/(label+'_summary.json'),dict(metadata=meta,summary=result))
    for kind,variants in result.items():
        for variant,r in variants.items():
            print(kind,variant,'mean',round(r['mean'],2),'std',round(r['std'],2),
                  'p95',round(r['p95'],2),'delta',round(r.get('paired',{}).get('delta',0),2),flush=True)


if __name__=='__main__':main()

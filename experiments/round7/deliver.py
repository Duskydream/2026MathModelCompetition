"""Replay the selected candidate, then synchronize the verified practice bundle."""
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SOURCE=ROOT/'analysis_b';PACKAGE=ROOT/'B题演练程序'
OUT=ROOT/'.local_archive/q4_round7';sys.path.insert(0,str(SOURCE))
from optimized import OptimizedPolicy
from simulator import LocalSimulator


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cfg=json.loads((SOURCE/'config.json').read_text());count=0
    with gzip.open(OUT/'holdout/synthetic_actions.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            entry=json.loads(line)
            if entry['row']['variant']!='cost_gate':continue
            sim=LocalSimulator(entry['sources'],cfg,entry['row']['seed'])
            policy=OptimizedPolicy(sim,cfg,4);status=policy.run()
            assert status==entry['status'],entry['row']
            assert sim.log==entry['actions'],entry['row']
            assert policy.certificates==entry['certificates'],entry['row']
            count+=1
            if count%50==0:print('production replay',count,flush=True)
    assert count==450
    for name in ['q4_policy.py','q4_optical.py','config.json','practice_robot.py']:
        shutil.copyfile(SOURCE/name,PACKAGE/name)
    manifest=json.loads((PACKAGE/'manifest.json').read_text(encoding='utf-8'))
    manifest['q4_optical.py']=sha(PACKAGE/'q4_optical.py')
    for name in manifest:manifest[name]=sha(PACKAGE/name)
    (PACKAGE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for name in ['q4_policy.py','q4_optical.py','model.py','optimized.py','q3_policy.py','config.json','practice_robot.py']:
        assert sha(SOURCE/name)==sha(PACKAGE/name),name
    (ROOT/'dist').mkdir(exist_ok=True)
    archive_path=ROOT/'dist/B题演练程序.zip'
    with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in [*manifest,'manifest.json']:archive.write(PACKAGE/name,PACKAGE.name+'/'+name)
    with zipfile.ZipFile(archive_path) as archive:
        for name in [*manifest,'manifest.json']:assert archive.read(PACKAGE.name+'/'+name)==(PACKAGE/name).read_bytes()
    result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','analysis_b','-p','test_*.py','-v'],
                          cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env=os.environ|{'PYTHONIOENCODING':'utf-8'})
    text=result.stdout+'\n'+result.stderr;(OUT/'delivery_tests.txt').write_text(text,encoding='utf-8');print(text)
    assert result.returncode==0
    tests=int(re.search(r'Ran (\d+) tests',text).group(1))
    summary=dict(replayed_cases=count,all_actions_and_certificates_match=True,tests_passed=tests,
                 package_matches_source=True,manifest_valid=True,zip_matches_package=True,official_runs=0,
                 sha256={name:sha(SOURCE/name) for name in ['q4_policy.py','q4_optical.py','config.json','practice_robot.py']})
    (HERE/'delivery_validation.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

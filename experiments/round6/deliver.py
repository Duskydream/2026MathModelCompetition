"""Synchronize the tested Q4 implementation and verify the practice manifest."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'analysis_b'
PACKAGE=ROOT/'B题演练程序'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    holdout=json.loads((HERE/'holdout_summary.json').read_text(encoding='utf-8'))
    for name,expected in holdout['metadata']['sha256'].items():
        assert sha(SOURCE/name)==expected,'Changed since holdout: '+name
    for name in ['q4_policy.py','config.json']:
        shutil.copyfile(SOURCE/name,PACKAGE/name)
    manifest=json.loads((PACKAGE/'manifest.json').read_text(encoding='utf-8'))
    for name in manifest:
        assert (PACKAGE/name).resolve().is_relative_to(PACKAGE.resolve()) and (PACKAGE/name).is_file(),name
        manifest[name]=sha(PACKAGE/name)
    (PACKAGE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    synchronized=['model.py','optimized.py','q3_policy.py','q4_policy.py','config.json',
                  'practice_robot.py','practice_launcher.py','practice_q3.py','practice_q4.py']
    for name in synchronized:
        assert sha(SOURCE/name)==sha(PACKAGE/name),name
    (ROOT/'dist').mkdir(exist_ok=True)
    archive_path=ROOT/'dist/B题演练程序.zip'
    with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in [*manifest,'manifest.json']:
            archive.write(PACKAGE/name,PACKAGE.name+'/'+name)
    with zipfile.ZipFile(archive_path) as archive:
        for name in [*manifest,'manifest.json']:
            assert archive.read(PACKAGE.name+'/'+name)==(PACKAGE/name).read_bytes(),name
    baseline=json.loads((HERE/'baseline/manifest.json').read_text(encoding='utf-8'))
    for name in ['model.py','optimized.py','q3_policy.py','simulator.py']:
        assert sha(SOURCE/name)==baseline['sha256'][name],name
    result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','analysis_b',
                           '-p','test_*.py','-v'],cwd=ROOT,text=True,capture_output=True,encoding='utf-8',
                          env=os.environ|{'PYTHONIOENCODING':'utf-8'})
    output=result.stdout+'\n'+result.stderr
    archive=ROOT/'.local_archive/q4_round6'
    archive.mkdir(parents=True,exist_ok=True)
    (archive/'delivery_tests.txt').write_text(output,encoding='utf-8')
    print(output)
    if result.returncode:
        raise RuntimeError('Delivery tests failed')
    count=int(re.search(r'Ran (\d+) tests',output).group(1))
    summary=dict(tests_passed=count,package_matches_source=True,manifest_valid=True,zip_matches_package=True,
                 shared_dependencies_unchanged=True,official_runs=0,
                 algorithm_sha256={name:sha(SOURCE/name) for name in synchronized})
    (HERE/'delivery_validation.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

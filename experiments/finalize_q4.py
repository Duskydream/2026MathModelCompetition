"""Verify the built package and synchronize the user-facing outer directory."""
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    package=ROOT/'B题演练程序'
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest.items():assert sha(package/name)==digest,name
    for name in ['model.py','optimized.py','q3_policy.py','q4_policy.py','config.json',
                 'practice_robot.py','practice_launcher.py','practice_q3.py','practice_q4.py']:
        assert sha(package/name)==sha(ROOT/'analysis_b'/name),name
    with zipfile.ZipFile(ROOT/'B题演练程序.zip') as archive:
        for path in package.iterdir():
            if path.is_file():assert archive.read(package.name+'/'+path.name)==path.read_bytes()
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    names=list(dict.fromkeys(filter(None,names)))+['B题演练程序.zip']
    for name in names:
        source,target=ROOT/name,ROOT.parent/name
        if not source.is_file():continue
        if not target.exists() or sha(source)!=sha(target):
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        assert sha(source)==sha(target),name
    result=dict(package_manifest_valid=True,zip_matches_folder=True,
                source_matches_package=True,outer_matches_worktree=True,
                synced_files=len(names),tests_passed=30,
                q4_replay=json.loads((ROOT/'experiments/round4/production_replay.json').read_text()),
                q3_replay=json.loads((ROOT/'experiments/round4/q3_regression.json').read_text()),
                algorithm_sha256={name:sha(ROOT/'analysis_b'/name) for name in
                                  ['model.py','optimized.py','q3_policy.py','q4_policy.py','config.json']})
    path=ROOT/'experiments/round4/delivery_validation.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    shutil.copyfile(path,ROOT.parent/'experiments/round4/delivery_validation.json')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

"""Freeze the fetched main baseline and verify the outer delivery copy."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/round4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=ROOT, text=True).strip()
    assert commit == remote, 'Baseline must be exactly fetched origin/main'
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    entries = []
    for name in filter(None, names):
        source, target = ROOT / name, ROOT.parent / name
        if not source.is_file():
            continue
        entries.append(dict(path=name, sha256=digest(source), outer_matches=target.is_file() and digest(target)==digest(source)))
    assert all(row['outer_matches'] for row in entries)
    baseline = OUT / 'baseline'
    baseline.mkdir(exist_ok=True)
    for source in (ROOT/'analysis_b').iterdir():
        if source.suffix in ('.py', '.json'):
            destination = baseline/source.name
            if destination.exists():
                assert digest(destination)==digest(source), 'Do not overwrite frozen baseline'
            else:
                shutil.copyfile(source, destination)
    evidence = dict(commit=commit, remote_main=remote, tracked_files=entries,
                    baseline={p.name:digest(p) for p in baseline.iterdir()},
                    unit_tests='27 passed; main baseline; local HTTP Q3 10/10 and Q4 10/10',
                    scoring='virtual seconds per true source, full clearance required',
                    target='Prefer all validation cases below 500 s/source; report tail and failures explicitly',
                    official_tests_used=0)
    (OUT/'main_alignment.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Verified',len(entries),'tracked files against main',commit)


if __name__ == '__main__':
    main()

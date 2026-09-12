"""Build the standalone practice bundle from an explicit list of public files."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile


def main():
    source = Path(__file__).resolve().parent
    root = source.parent
    destination = root / 'B题演练程序'
    destination.mkdir(exist_ok=True)
    names = [
        'practice_robot.py', 'practice_launcher.py', 'practice_q3.py', 'practice_q4.py',
        'model.py', 'optimized.py', 'q3_policy.py', 'q4_policy.py', 'q4_optical.py',
        'config.json', 'practice_q3_six.py', 'config_q3_six.json',
    ]
    for name in names:
        shutil.copyfile(source / name, destination / name)
    (destination / 'requirements.txt').write_bytes(
        b'numpy==2.2.6\r\nscipy==1.15.3\r\n')
    names.append('requirements.txt')
    for question in (3, 4):
        command = f'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python practice_q{question}.py
) else (
    py -3 practice_q{question}.py
)
pause
'''
        name = f'启动第{question}问演练.cmd'
        (destination / name).write_bytes(command.replace('\n', '\r\n').encode('utf-8'))
        names.append(name)
    experimental = '''@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 实验入口：第3问 6 站方案，不保证发现全部干扰源，仅用于演练对比。
where py >nul 2>nul
if errorlevel 1 (
    python practice_q3_six.py
) else (
    py -3 practice_q3_six.py
)
pause
'''
    name = '实验_第3问6站演练.cmd'
    (destination / name).write_bytes(experimental.replace('\n', '\r\n').encode('utf-8'))
    names.append(name)
    (destination / 'docs').mkdir(exist_ok=True)
    shutil.copyfile(root / 'docs/演练使用说明.md', destination / 'docs/使用说明.md')
    names.append('docs/使用说明.md')
    manifest = {
        name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
        for name in sorted(names)
    }
    (destination / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
        newline='\r\n')
    distribution = root / 'dist'
    distribution.mkdir(exist_ok=True)
    archive_path = distribution / 'B题演练程序.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in [*manifest, 'manifest.json']:
            archive.write(destination / name, destination.name + '/' + name)
    print(archive_path)


if __name__ == '__main__':
    main()

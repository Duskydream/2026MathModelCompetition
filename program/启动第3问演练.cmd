@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python practice_q3.py
) else (
    py -3 practice_q3.py
)
pause

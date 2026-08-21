@echo off
REM 사내 지침 챗봇 실행 (Windows)
chcp 65001 > nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

%PYTHON% run_app.py
pause

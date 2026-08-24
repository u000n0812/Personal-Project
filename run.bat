@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM GuideBot - local guideline-document chatbot launcher (Windows)
REM Binds only to 127.0.0.1; not reachable from other machines on the network.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo During setup, check "Add Python to PATH", then run this file again.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/3] Creating a Python virtual environment ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

REM Always (re)install requirements, not just on first setup. This keeps the
REM .venv in sync whenever requirements.txt gains a new dependency, and
REM guarantees packages land in the SAME Python this app actually runs with
REM (a very common mistake is running "pip install X" in a different
REM terminal/Python than the one .venv uses - this line prevents that).
echo [2/3] Checking required libraries (this is quick if nothing changed) ...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install libraries. Check your internet connection and try again.
    pause
    exit /b 1
)

echo [3/3] GuideBot is starting. Open http://127.0.0.1:8501 in your browser.
echo (Press Ctrl+C in this window to stop the server.)
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

endlocal

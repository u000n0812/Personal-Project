@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Local guideline-document assistant launcher (Windows)
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
    call ".venv\Scripts\activate.bat"
    echo [2/3] Installing required libraries ...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install libraries. Check your internet connection and try again.
        pause
        exit /b 1
    )
) else (
    call ".venv\Scripts\activate.bat"
)

echo [3/3] Open http://127.0.0.1:8501 in your browser.
echo (Press Ctrl+C in this window to stop the server.)
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

endlocal

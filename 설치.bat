@echo off
REM ===========================================================================
REM  사내 지침 챗봇 - 원클릭 자동 설치 (Windows)
REM
REM  이 파일을 더블클릭하면 아래를 순서대로 자동 처리합니다.
REM    1) Python 확인 (없으면 자동 설치)
REM    2) 가상환경 생성 + 필요한 라이브러리 설치
REM    3) Ollama 설치 + LLM 모델 + 임베딩 모델 자동 준비
REM    4) 프로그램 실행
REM ===========================================================================
chcp 65001 > nul
cd /d "%~dp0"
title 사내 지침 챗봇 - 자동 설치
setlocal enabledelayedexpansion

echo.
echo ====================================================================
echo   사내 지침 챗봇 - 자동 설치
echo ====================================================================
echo.
echo   설치에는 10~30분 정도 걸릴 수 있습니다. (모델 다운로드 포함)
echo   창을 닫지 말고 기다려 주세요.
echo.

REM --------------------------------------------------------------------
REM  1) Python 확인
REM --------------------------------------------------------------------
echo ====================================================================
echo   [1/4] Python 확인
echo ====================================================================

set "PYTHON="
for %%C in ("py -3" "python") do (
    if not defined PYTHON (
        %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if !errorlevel! equ 0 set "PYTHON=%%~C"
    )
)

if defined PYTHON (
    echo   설치됨:
    !PYTHON! --version
) else (
    echo   Python 3.10 이상이 없습니다. 자동 설치를 시작합니다.
    set "PYINST=%TEMP%\python-installer.exe"
    echo   다운로드 중...
    powershell -NoProfile -Command ^
        "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python-installer.exe'"
    if not exist "!PYINST!" (
        echo.
        echo   [설치 중단] Python 다운로드에 실패했습니다.
        echo   https://www.python.org/downloads/ 에서 직접 설치한 뒤 다시 실행해 주세요.
        goto :fail
    )
    echo   설치 중... ^(몇 분 걸립니다^)
    "!PYINST!" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
    del /q "!PYINST!" 2>nul

    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    if not exist "!PYTHON!" (
        echo.
        echo   [설치 중단] Python 설치를 확인하지 못했습니다.
        echo   이 창을 닫고 다시 실행해 주세요.
        goto :fail
    )
    echo   설치 완료.
)

REM --------------------------------------------------------------------
REM  2) 가상환경 + 라이브러리
REM --------------------------------------------------------------------
echo.
echo ====================================================================
echo   [2/4] 라이브러리 설치
echo ====================================================================

if not exist ".venv\Scripts\python.exe" (
    echo   가상환경 생성 중...
    !PYTHON! -m venv .venv
    if errorlevel 1 (
        echo   [설치 중단] 가상환경 생성에 실패했습니다.
        goto :fail
    )
)
set "VPY=.venv\Scripts\python.exe"

echo   필요한 라이브러리 설치 중... ^(몇 분 걸립니다^)
"%VPY%" -m pip install --upgrade pip --quiet
"%VPY%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo   [설치 중단] 라이브러리 설치에 실패했습니다.
    goto :fail
)
echo   완료.

REM --------------------------------------------------------------------
REM  3) Ollama + 모델 자동 준비
REM --------------------------------------------------------------------
echo.
echo ====================================================================
echo   [3/4] AI 모델 준비
echo ====================================================================

"%VPY%" scripts\setup.py
if errorlevel 1 goto :fail

REM --------------------------------------------------------------------
REM  4) 실행
REM --------------------------------------------------------------------
echo.
echo ====================================================================
echo   [4/4] 프로그램 실행
echo ====================================================================
echo.
echo   브라우저에서 http://127.0.0.1:8501 이 열립니다.
echo   다음부터는 run.bat 을 더블클릭하면 바로 실행됩니다.
echo.

"%VPY%" run_app.py
goto :end

:fail
echo.
echo   설치가 완료되지 않았습니다. 위 메시지를 확인해 주세요.
echo.
pause
exit /b 1

:end
pause

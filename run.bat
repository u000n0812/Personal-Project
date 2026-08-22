@echo off
REM 사내 지침문서 어시스턴트 실행 (Windows)
REM 127.0.0.1 에만 Binding 되며 외부에서는 접속할 수 없습니다.

setlocal
cd /d "%~dp0"

if not exist ".venv" (
    echo [1/3] Python 가상환경을 만듭니다...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [2/3] 필요한 라이브러리를 설치합니다...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [3/3] 브라우저에서 http://127.0.0.1:8501 로 접속하세요.
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
endlocal

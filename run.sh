#!/usr/bin/env bash
# 사내 지침문서 어시스턴트 실행 (macOS / Linux)
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[1/3] Python 가상환경을 만듭니다..."
  python3 -m venv .venv
  source .venv/bin/activate
  echo "[2/3] 필요한 라이브러리를 설치합니다..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
else
  source .venv/bin/activate
fi

echo "[3/3] 브라우저에서 http://127.0.0.1:8501 로 접속하세요."
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

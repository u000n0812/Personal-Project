#!/usr/bin/env bash
# GuideBot - 사내 지침문서 조회 챗봇 실행 (macOS / Linux)
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[1/3] Python 가상환경을 만듭니다..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# 매번 requirements.txt를 다시 설치한다(이미 설치된 건 순식간에 건너뜀).
# requirements.txt에 새 항목이 추가돼도 .venv가 뒤처지지 않도록 하고,
# "다른 터미널/파이썬에 pip install 했더니 반영이 안 된다"는 문제를 막는다.
echo "[2/3] 필요한 라이브러리를 확인합니다(달라진 게 없으면 금방 끝납니다)..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

echo "[3/3] GuideBot을 시작합니다. 브라우저에서 http://127.0.0.1:8501 로 접속하세요."
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

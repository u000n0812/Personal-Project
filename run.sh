#!/usr/bin/env bash
# 사내 지침 챗봇 실행 (macOS / Linux)
set -e
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

"$PYTHON" run_app.py

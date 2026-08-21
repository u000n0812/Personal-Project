"""프로그램 실행 진입점.

    python run_app.py

Streamlit 을 127.0.0.1 에만 Binding 해 실행한다(요구사항 13).
필요한 폴더와 SQLite DB 는 최초 실행 시 자동 생성된다(요구사항 21).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app import db, netguard  # noqa: E402
from app.config import DATA_DIR, ensure_directories, load_settings  # noqa: E402

HOST = "127.0.0.1"
PORT = "8501"


def preflight() -> bool:
    ensure_directories()
    db.init_db()
    load_settings()
    netguard.apply_offline_env(offline=True)

    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("[오류] streamlit 이 설치되어 있지 않습니다.")
        print("       pip install -r requirements.txt")
        return False
    return True


def main() -> int:
    if not preflight():
        return 1

    print("=" * 60)
    print(" 사내 지침 챗봇 (완전 로컬 실행)")
    print("=" * 60)
    print(f" 데이터 폴더 : {DATA_DIR}")
    print(f" 접속 주소   : http://{HOST}:{PORT}")
    print(" 종료        : 이 창에서 Ctrl+C")
    print("=" * 60)

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT / "ui" / "streamlit_app.py"),
        "--server.address",
        HOST,
        "--server.port",
        PORT,
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    try:
        return subprocess.call(command, cwd=str(ROOT))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

"""테스트 공통 준비.

테스트는 실제 data 폴더를 건드리지 않도록 임시 폴더를 사용한다.
sopbot 패키지를 import 하기 전에 환경변수를 설정해야 한다.
"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="sopbot_test_"))
os.environ.setdefault("SOPBOT_DATA_DIR", str(TEST_DATA_DIR))
os.environ.setdefault("SOPBOT_BACKUP_DIR", str(TEST_DATA_DIR / "backup"))

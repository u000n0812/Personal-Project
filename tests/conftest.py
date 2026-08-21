"""테스트 공통 설정.

- 데이터 폴더를 임시 디렉터리로 돌려 실제 data/ 를 건드리지 않는다.
- 임베딩은 모델 파일이 필요 없는 HashingEmbedder 를 사용한다.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TMP_DATA = Path(tempfile.mkdtemp(prefix="chatbot-test-"))
os.environ["CHATBOT_DATA_DIR"] = str(_TMP_DATA)
os.environ["CHATBOT_EMBEDDER"] = "hash"

from app import db  # noqa: E402
from app.config import Settings, ensure_directories  # noqa: E402
from app.pipeline import DocumentIndex  # noqa: E402

SAMPLE_SOP = """External Data Transfer Specification

1. 목적
본 문서는 External Data 를 Vendor 와 주고받을 때 지켜야 할 절차를 정의한다.

2. 적용 범위
모든 임상 프로젝트의 외부 데이터 전달에 적용한다.

5. Data Transfer
5.1 전달 준비
Data Provider 는 전달 전에 Data Transfer Agreement 승인 여부를 확인한다.

5.3 Encryption Rule
Data Provider 는 파일을 반드시 암호화하여 전달한다.
Password 는 파일과 분리하여 별도의 Email 로 전달한다.
Password 는 최소 12자리 이상으로 설정한다.

6. 승인
External Data 전달은 Data Manager 승인 후 Project Manager 최종 승인을 받는다.
"""

SAMPLE_DBLOCK = """Database Lock Guideline

1. 개요
DBL 은 Database Lock 을 의미하며 통계 분석 전에 수행한다.

3. DB Lock 전 확인 항목
DB Lock 전에 다음 항목을 확인한다.
모든 Query 가 종결되었는지 확인한다.
SAE Reconciliation 이 완료되었는지 확인한다.
External Data Reconciliation 이 완료되었는지 확인한다.
Coding 이 완료되고 승인되었는지 확인한다.

4. 승인
DB Lock 은 Data Manager, 통계담당자, Project Manager 승인이 필요하다.
"""


@pytest.fixture(autouse=True)
def clean_data_dir():
    """테스트마다 데이터 폴더를 비운다."""
    import sys

    # Streamlit 캐시가 이전 테스트의 인덱스를 물고 있지 않도록 정리한다.
    if "streamlit" in sys.modules:  # pragma: no cover - UI 테스트에서만 동작
        sys.modules["streamlit"].cache_resource.clear()
    if _TMP_DATA.exists():
        for child in _TMP_DATA.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    ensure_directories()
    db.init_db()
    yield


@pytest.fixture
def settings() -> Settings:
    return Settings(chunk_size=400, chunk_overlap=80, top_k=5, score_threshold=0.2)


@pytest.fixture
def index(settings: Settings) -> DocumentIndex:
    return DocumentIndex(settings)


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """테스트용 지침문서 2건이 들어있는 폴더."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "External_Data_Transfer_Specification_v2.1.txt").write_text(
        SAMPLE_SOP, encoding="utf-8"
    )
    (folder / "Database_Lock_Guideline_v1.4.txt").write_text(
        SAMPLE_DBLOCK, encoding="utf-8"
    )
    return folder


@pytest.fixture
def data_dir() -> Path:
    return _TMP_DATA

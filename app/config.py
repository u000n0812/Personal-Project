"""설정 및 데이터 경로 관리.

설정은 ``data/config.json`` 에 저장되며, 파일이 없으면 기본값으로 자동 생성된다.
설정 항목은 요구사항(14. Settings)대로 최소한만 노출한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# 프로젝트 루트 = 이 파일(app/config.py)의 상위 폴더
ROOT_DIR = Path(__file__).resolve().parent.parent

# 데이터 폴더 위치는 환경변수로만 바꿀 수 있게 한다(테스트/다중 프로필용).
DATA_DIR = Path(os.environ.get("CHATBOT_DATA_DIR", ROOT_DIR / "data")).resolve()

DOCUMENTS_DIR = DATA_DIR / "documents"
INDEX_DIR = DATA_DIR / "index"
DATABASE_DIR = DATA_DIR / "database"
LOGS_DIR = DATA_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backup"
MODELS_DIR = DATA_DIR / "models"

DB_PATH = DATABASE_DIR / "metadata.sqlite3"
CONFIG_PATH = DATA_DIR / "config.json"
SYNONYMS_PATH = DATA_DIR / "synonyms.json"

# 지원 문서 확장자
REQUIRED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
OPTIONAL_EXTENSIONS = {".xlsx", ".pptx"}
SUPPORTED_EXTENSIONS = REQUIRED_EXTENSIONS | OPTIONAL_EXTENSIONS

# 검색 결과를 찾지 못했을 때 사용하는 고정 문구(요구사항 12)
NO_ANSWER_MESSAGE = "등록된 지침문서에서는 해당 내용을 확인하지 못했습니다."
WEAK_ANSWER_MESSAGE = (
    "관련 내용으로 다음 문서가 검색되었지만 질문에 대한 명확한 절차는 확인되지 않습니다."
)


@dataclass
class Settings:
    """사용자 조정 가능 설정."""

    # --- LLM (로컬 Ollama) ---
    llm_model: str = "qwen2.5:7b-instruct"
    ollama_host: str = "http://127.0.0.1:11434"
    temperature: float = 0.1
    answer_length: str = "보통"  # 짧게 / 보통 / 자세히
    history_turns: int = 3  # 대화 Context로 전달할 최근 turn 수

    # --- Embedding (로컬 sentence-transformers) ---
    embedding_model: str = "intfloat/multilingual-e5-small"

    # --- 검색 ---
    top_k: int = 5
    candidate_k: int = 30
    score_threshold: float = 0.35  # Hybrid 최종 점수 기준
    vector_weight: float = 0.6  # 0=키워드만, 1=벡터만

    # --- Chunking ---
    chunk_size: int = 900  # 글자 수 기준
    chunk_overlap: int = 150

    # --- 보안 ---
    strict_offline: bool = True  # loopback 이외 네트워크 연결 차단

    # 내부용(설정 화면에 노출하지 않음)
    _unknown: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    @property
    def answer_max_sentences(self) -> int:
        return {"짧게": 4, "보통": 8, "자세히": 16}.get(self.answer_length, 8)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("_unknown", None)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)} - {"_unknown"}
        kwargs = {k: v for k, v in data.items() if k in known}
        unknown = {k: v for k, v in data.items() if k not in known}
        obj = cls(**kwargs)
        obj._unknown = unknown
        return obj


def ensure_directories() -> None:
    """최초 실행 시 필요한 폴더를 자동 생성한다(요구사항 21)."""
    for path in (
        DATA_DIR,
        DOCUMENTS_DIR,
        INDEX_DIR,
        DATABASE_DIR,
        LOGS_DIR,
        BACKUP_DIR,
        MODELS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    ensure_directories()
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return Settings.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            # 설정 파일이 깨진 경우 기본값으로 복구한다.
            pass
    settings = Settings()
    save_settings(settings)
    return settings


def save_settings(settings: Settings) -> None:
    ensure_directories()
    payload = {**settings._unknown, **settings.to_dict()}
    CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

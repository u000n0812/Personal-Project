"""설정 값과 데이터 저장 경로 관리.

설정은 data/config.json 에 저장되며, 없으면 기본값으로 자동 생성된다.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 테스트나 다중 프로필 실행을 위해 데이터 폴더를 환경변수로 바꿀 수 있다.
# 이전 이름(SOPBOT_*)으로 설정해 둔 환경도 그대로 동작하게 한다.
DATA_DIR = Path(
    os.environ.get("GUIDEBOT_DATA_DIR")
    or os.environ.get("SOPBOT_DATA_DIR")
    or PROJECT_ROOT / "data"
).resolve()

DOCUMENTS_DIR = DATA_DIR / "documents"   # 원본 문서 사본
INDEX_DIR = DATA_DIR / "index"           # Vector Index
DATABASE_DIR = DATA_DIR / "database"     # SQLite
LOGS_DIR = DATA_DIR / "logs"             # 운영 로그(민감정보 미기록)
CACHE_DIR = DATA_DIR / "cache"           # 로컬 모델 캐시
BACKUP_DIR = Path(
    os.environ.get("GUIDEBOT_BACKUP_DIR")
    or os.environ.get("SOPBOT_BACKUP_DIR")
    or PROJECT_ROOT / "backup"
).resolve()

DB_PATH = DATABASE_DIR / "guidebot.sqlite3"
LEGACY_DB_PATH = DATABASE_DIR / "sopbot.sqlite3"   # 이전 버전에서 만든 DB
CONFIG_PATH = DATA_DIR / "config.json"
SYNONYM_PATH = DATA_DIR / "synonyms.json"

# 근거를 찾지 못했을 때 사용하는 고정 답변
NO_EVIDENCE_ANSWER = "등록된 지침문서에서는 해당 내용을 확인하지 못했습니다."
WEAK_EVIDENCE_ANSWER = (
    "관련 내용으로 다음 문서가 검색되었지만 질문에 대한 명확한 절차는 확인되지 않습니다."
)
# 검색은 성공했지만 모델 답변이 문서 내용과 맞지 않아 폐기한 경우
UNGROUNDED_ANSWER = (
    "AI가 만든 답변이 지침문서 내용과 맞지 않아 표시하지 않았습니다. "
    "아래에 검색된 지침문서 원문을 그대로 보여드리니 직접 확인해 주세요."
)


@dataclass
class Settings:
    """사용자가 Settings 화면에서 조정하는 값."""

    # --- LLM (로컬 실행) ---
    ollama_host: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    temperature: float = 0.1
    llm_timeout_sec: int = 180

    # --- Embedding (로컬 실행) ---
    # auto -> Ollama(bge-m3) 우선, 없으면 sentence-transformers, 그것도 없으면 hashing
    embed_backend: str = "auto"
    ollama_embed_model: str = "bge-m3"                    # 권장(Ollama에서 실행)
    embed_model: str = "intfloat/multilingual-e5-small"   # sentence-transformers 사용 시

    # --- 검색 ---
    top_k: int = 5
    candidate_k: int = 20
    score_threshold: float = 0.0        # 0이면 Embedding 모델별 권장값을 자동 사용
    keyword_weight: float = 0.4
    min_keyword_coverage: float = 0.3   # 질문 단어가 문서에서 확인된 비율의 최소값
    high_confidence: float = 0.9        # 이 이상이면 "해당 내용을 찾았습니다"
    medium_confidence: float = 0.5      # 이 이상이면 "유사한 내용을 찾았습니다(확인 필요)"
    min_score_ratio: float = 0.3        # 1위 대비 이 비율 미만인 결과는 출처에서 제외
    include_superseded: bool = False

    # --- 답변 ---
    strict_mode: bool = True            # 지침문서 내용만 답변(범위 검사 + 근거 검증)
    min_sentence_support: float = 0.45  # 답변 문장이 문서 내용과 일치해야 하는 최소 비율
    answer_length: str = "보통"  # 짧게 | 보통 | 자세히
    max_context_chars: int = 6000
    history_turns: int = 3

    # --- 문서 처리 ---
    chunk_size: int = 900
    chunk_overlap: int = 150

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or CONFIG_PATH
        if not path.exists():
            settings = cls()
            settings.save(path)
            return settings
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def answer_max_sentences(self) -> int:
        return {"짧게": 4, "보통": 8, "자세히": 16}.get(self.answer_length, 8)


def ensure_dirs() -> None:
    """최초 실행 시 필요한 폴더를 자동 생성한다."""
    for directory in (
        DATA_DIR,
        DOCUMENTS_DIR,
        INDEX_DIR,
        DATABASE_DIR,
        LOGS_DIR,
        CACHE_DIR,
        BACKUP_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


# 기본 동의어 사전: "DBL" == "DB Lock" == "Database Lock" 같은 표현 차이를 흡수한다.
DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "dbl": ["db lock", "database lock", "디비 락", "데이터베이스 락"],
    "db lock": ["dbl", "database lock", "디비 락"],
    "database lock": ["dbl", "db lock"],
    "sop": ["표준작업절차", "표준 작업 절차", "업무절차서", "지침"],
    "external data": ["외부 데이터", "외부데이터", "익스터널 데이터"],
    "edc": ["electronic data capture", "전자자료수집"],
    "crf": ["case report form", "증례기록서"],
    "qc": ["quality control", "품질관리"],
    "qa": ["quality assurance", "품질보증"],
    "sae": ["serious adverse event", "중대이상반응"],
    "pi": ["principal investigator", "책임연구자"],
    "vendor": ["벤더", "외주업체", "협력업체"],
    "approval": ["승인", "결재"],
    "암호화": ["encryption", "encrypt", "password protect"],
    "전달": ["transfer", "송부", "발송"],
}


def load_synonyms(path: Path | None = None) -> dict[str, list[str]]:
    """동의어 사전을 읽는다. 파일이 없으면 기본값으로 생성한다."""
    path = path or SYNONYM_PATH
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(DEFAULT_SYNONYMS, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return dict(DEFAULT_SYNONYMS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SYNONYMS)
    return {str(k).lower(): [str(v) for v in vals] for k, vals in raw.items()}

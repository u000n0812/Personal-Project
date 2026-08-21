"""한국어/영문 혼용 문서를 위한 토크나이저와 동의어 확장 (요구사항 9).

외부 형태소 분석기(설치 부담이 큰 라이브러리)를 쓰지 않고,
"단어 + 한글 2-gram" 방식으로 조사/어미 변화를 흡수한다.

  "절차가"  -> 절차가, 절차, 차가  (2-gram)
  "Database Lock" -> database, lock
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import SYNONYMS_PATH

TOKEN_PATTERN = re.compile(r"[A-Za-z]+|[0-9]+(?:\.[0-9]+)*|[가-힣]+")

# 업무 지침문서에서 자주 쓰이는 기본 동의어(사용자가 data/synonyms.json 으로 확장 가능)
DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "dbl": ["database lock", "db lock", "디비락", "데이터베이스 락"],
    "db lock": ["dbl", "database lock", "데이터베이스 락"],
    "database lock": ["dbl", "db lock", "데이터베이스 락"],
    "sop": ["표준작업절차", "표준 업무 절차", "standard operating procedure"],
    "ext data": ["external data", "외부데이터", "외부 데이터"],
    "external data": ["ext data", "외부데이터", "외부 데이터"],
    "edc": ["electronic data capture", "전자자료수집"],
    "qc": ["quality control", "품질관리"],
    "qa": ["quality assurance", "품질보증"],
    "crf": ["case report form", "증례기록서"],
    "ap": ["analysis plan", "분석계획서"],
    "sdtm": ["study data tabulation model"],
    "vendor": ["업체", "공급업체", "협력업체"],
    "암호화": ["encryption", "encrypt", "password protect"],
    "승인": ["approval", "approve", "결재"],
    "전달": ["transfer", "전송", "송부", "delivery"],
    "절차": ["procedure", "process", "프로세스"],
}


def tokenize(text: str, *, with_ngrams: bool = True) -> list[str]:
    """검색용 토큰 목록을 만든다."""
    tokens: list[str] = []
    for match in TOKEN_PATTERN.findall(text.lower()):
        tokens.append(match)
        if with_ngrams and len(match) >= 3 and re.match(r"^[가-힣]+$", match):
            # 한글 단어는 2-gram 을 추가해 조사/어미 변형을 흡수한다.
            tokens.extend(match[i : i + 2] for i in range(len(match) - 1))
    return tokens


def load_synonyms() -> dict[str, list[str]]:
    """기본 동의어 + 사용자 정의 동의어(data/synonyms.json)를 합쳐 반환한다."""
    synonyms = {key: list(value) for key, value in DEFAULT_SYNONYMS.items()}
    path = Path(SYNONYMS_PATH)
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
            for key, value in user.items():
                key = str(key).lower().strip()
                values = [str(v).lower().strip() for v in value] if isinstance(value, list) else []
                synonyms.setdefault(key, [])
                for item in values:
                    if item not in synonyms[key]:
                        synonyms[key].append(item)
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            pass
    return synonyms


def expand_query(query: str, synonyms: dict[str, list[str]] | None = None) -> str:
    """질문에 동의어를 덧붙여 표현 차이를 흡수한다(키워드 검색 전용)."""
    table = synonyms if synonyms is not None else load_synonyms()
    lowered = query.lower()
    additions: list[str] = []
    for key, values in table.items():
        if key in lowered:
            additions.extend(values)
    if not additions:
        return query
    unique = [item for index, item in enumerate(additions) if item not in additions[:index]]
    return f"{query} {' '.join(unique)}"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()

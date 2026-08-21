"""문서 버전 인식 (요구사항 7).

파일명에서 버전을 추출해 같은 지침의 다른 버전을 하나의 ``doc_key`` 로 묶는다.

  SOP_DataManagement_v1.0.pdf  -> doc_key=sop_datamanagement, version=1.0
  SOP_DataManagement_v2.0.pdf  -> doc_key=sop_datamanagement, version=2.0

최신 버전이 기본 검색 대상(active)이 되고, 과거 버전은 비활성 상태로 남는다.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSION_PATTERNS = [
    re.compile(r"[_\-\s(\[]v(?:er)?[._\-\s]?(\d+(?:[._]\d+)*)\)?\]?\s*$", re.I),
    re.compile(r"[_\-\s(\[]rev[._\-\s]?(\d+(?:[._]\d+)*)\)?\]?\s*$", re.I),
    re.compile(r"[_\-\s](\d+\.\d+(?:\.\d+)*)\s*$"),
    re.compile(r"[_\-\s(\[](20\d{6})\)?\]?\s*$"),  # 20240131 형태의 일자 버전
]


def parse_version(filename: str) -> tuple[str, str]:
    """파일명에서 (버전 제거된 이름, 버전 문자열)을 반환한다."""
    stem = Path(filename).stem.strip()
    for pattern in VERSION_PATTERNS:
        match = pattern.search(stem)
        if match:
            version = match.group(1).replace("_", ".")
            base = stem[: match.start()].strip(" _-([")
            return (base or stem), version
    return stem, ""


def version_sort_key(version: str) -> str:
    """문자열 정렬만으로 버전 비교가 가능하도록 zero-padding 한다.

    '1.10' -> '000001.000010' (즉 '1.9' 보다 크다)
    버전이 없으면 가장 낮은 값으로 취급한다.
    """
    if not version:
        return "000000"
    parts = re.split(r"[.]", version)
    padded = [f"{int(part):06d}" if part.isdigit() else part.rjust(6, "0") for part in parts]
    return ".".join(padded)


def doc_key_of(filename: str) -> str:
    """버전을 제외한 문서 식별자(대소문자/공백 무시)."""
    base, _ = parse_version(filename)
    return re.sub(r"[\s_\-]+", "", base).lower()


def pretty_title(base: str) -> str:
    """파일명 스타일(밑줄/연속 공백)을 사람이 읽기 좋은 제목으로 다듬는다."""
    return re.sub(r"\s{2,}", " ", base.replace("_", " ")).strip()


def describe(filename: str) -> dict:
    base, version = parse_version(filename)
    return {
        "doc_key": doc_key_of(filename),
        "title": pretty_title(base),
        "version": version,
        "version_key": version_sort_key(version),
    }

"""파일명에서 문서 식별자 / 버전 / 제목을 해석한다.

예) SOP_DataManagement_v1.1.pdf
    doc_key = "sop_datamanagement"
    version = "1.1"
    title   = "SOP DataManagement"
"""

from __future__ import annotations

import re
from pathlib import Path

# _v1.0 / -V2 / (v1.2) / _rev3 / _ver 1.1 등 흔한 버전 표기를 인식한다
_VERSION_PATTERNS = (
    re.compile(r"[_\-\s(\[]+v(?:er)?[\._\-\s]?(\d+(?:\.\d+)*)[)\]]?\s*$", re.IGNORECASE),
    re.compile(r"[_\-\s(\[]+rev(?:ision)?[\._\-\s]?(\d+(?:\.\d+)*)[)\]]?\s*$", re.IGNORECASE),
    re.compile(r"[_\-\s(\[]+(?:버전|개정)[\._\-\s]?(\d+(?:\.\d+)*)[)\]]?\s*$"),
)

DEFAULT_VERSION = "1.0"


def parse_doc_name(file_name: str) -> tuple[str, str, str]:
    """파일명을 (doc_key, version, title)로 분해한다."""
    stem = Path(file_name).stem.strip()
    version = ""
    base = stem
    for pattern in _VERSION_PATTERNS:
        match = pattern.search(base)
        if match:
            version = match.group(1)
            base = base[: match.start()].strip()
            break
    if not version:
        version = DEFAULT_VERSION
    title = re.sub(r"[_\-]+", " ", base).strip() or stem
    doc_key = re.sub(r"[^0-9a-z가-힣]+", "_", base.lower()).strip("_") or stem.lower()
    return doc_key, version, title


def version_sort_key(version: str) -> tuple[int, ...]:
    """'1.10' > '1.9' 가 되도록 숫자 단위로 비교 가능한 key를 만든다."""
    parts = re.findall(r"\d+", version or "")
    return tuple(int(p) for p in parts) or (0,)


def is_newer_version(candidate: str, current: str) -> bool:
    return version_sort_key(candidate) > version_sort_key(current)

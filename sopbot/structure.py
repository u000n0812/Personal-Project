"""문서 제목(Heading) 판별 로직.

텍스트 추출 단계(extract)와 Chunk 분할 단계(chunk)가 함께 사용하므로
별도 모듈로 분리한다.
"""

from __future__ import annotations

import re

# "5.3 Data Transfer", "3.1.2 검토", "1) 개요"
_NUMBERED_HEADING = re.compile(r"^\s*(\d+(?:\.\d+){0,3})[.)]?\s+(\S.*)$")
# "Chapter 3", "Section 5", "Appendix A", "제 3 장", "제5조"
_LABELED_HEADING = re.compile(
    r"^\s*(chapter|section|appendix|부록|제\s*\d+\s*[장절조항])\b",
    re.IGNORECASE,
)

MAX_HEADING_LEN = 90


def detect_heading(text: str) -> tuple[bool, int, str]:
    """문단이 제목인지 판단하고 (여부, level, 제목텍스트)를 반환한다."""
    stripped = text.strip()
    if not stripped or len(stripped) > MAX_HEADING_LEN or "\n" in stripped:
        return False, 0, ""

    match = _NUMBERED_HEADING.match(stripped)
    if match:
        number, title = match.group(1), match.group(2)
        # "1. 문장이 길게 이어지는 본문"은 제목으로 보지 않는다.
        if len(title) <= MAX_HEADING_LEN and not title.endswith((".", "다.", "요.")):
            return True, number.count(".") + 1, stripped
    if _LABELED_HEADING.match(stripped):
        return True, 1, stripped
    # 마침표 없이 짧고 콜론으로 끝나는 줄(예: "5.3 Data Transfer:")
    if len(stripped) <= 40 and stripped.endswith(":"):
        return True, 2, stripped.rstrip(":")
    # 영문 대문자 제목 (예: "DATA TRANSFER PROCEDURE")
    letters = [c for c in stripped if c.isalpha()]
    ascii_letters = [c for c in letters if c.isascii()]
    if (
        len(stripped) <= 60
        and len(ascii_letters) >= 3
        and len(ascii_letters) == len(letters)   # 한글이 섞인 문장은 제외
        and all(c.isupper() for c in ascii_letters)
    ):
        return True, 1, stripped
    return False, 0, ""


def split_lines_by_heading(text: str) -> list[tuple[str, bool, int]]:
    """여러 줄 텍스트를 (조각, 제목여부, level) 목록으로 나눈다.

    PDF처럼 서식 정보가 없는 문서에서 제목 줄을 찾아내기 위해 사용한다.
    """
    pieces: list[tuple[str, bool, int]] = []
    body: list[str] = []

    def flush_body() -> None:
        if body:
            joined = "\n".join(body).strip()
            if joined:
                pieces.append((joined, False, 0))
            body.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_heading, level, heading_text = detect_heading(stripped)
        if is_heading:
            flush_body()
            pieces.append((heading_text, True, level))
        else:
            body.append(stripped)
    flush_body()
    return pieces

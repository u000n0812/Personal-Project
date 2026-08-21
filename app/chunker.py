"""구조 보존형 Chunking (요구사항 8 / Phase 3).

단순히 N글자로 자르지 않고 다음 규칙을 따른다.

1. Section(제목 경로)이 바뀌면 반드시 Chunk를 나눈다.
2. Section 안에서는 문단 단위로 이어붙이되 ``chunk_size`` 를 넘지 않게 한다.
3. 같은 Section 안에서만 ``chunk_overlap`` 만큼 앞 내용을 겹쳐 문맥을 유지한다.
4. 표(table)는 가능하면 통째로 유지하고, 너무 크면 헤더 행을 반복하며 나눈다.
5. 각 Chunk 는 제목 경로/페이지 정보를 metadata 로 갖고, 본문 앞에도 제목을
   붙여 검색 품질을 높인다.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from app.extractors import Block

HEADING_PREFIX = "[문서 위치] "


def _section_of(heading_path: Sequence[str]) -> str:
    return heading_path[-1] if heading_path else ""


def _compose(heading_path: Sequence[str], body: str) -> str:
    if heading_path:
        return f"{HEADING_PREFIX}{' > '.join(heading_path)}\n{body.strip()}"
    return body.strip()


def _tail_overlap(text: str, overlap: int) -> str:
    """직전 chunk 의 끝부분을 overlap 만큼 잘라 문장 경계에 맞춰 반환한다."""
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    tail = text[-overlap:]
    for separator in ("\n", ". ", "다. ", "! ", "? "):
        position = tail.find(separator)
        if 0 <= position < len(tail) - 10:
            return tail[position + len(separator):]
    return tail


def _split_table(text: str, chunk_size: int) -> list[str]:
    """큰 표를 헤더 행을 반복하면서 나눈다."""
    lines = text.splitlines()
    if not lines:
        return []
    header = lines[0]
    # 헤더 행이 매 조각마다 반복되므로 그만큼 본문 예산을 줄인다.
    budget = max(80, chunk_size - len(header) - 1)
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in lines[1:]:
        if size + len(line) > budget and current:
            parts.append("\n".join([header, *current]))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    parts.append("\n".join([header, *current]) if current else header)
    return parts


def chunk_blocks(
    blocks: Iterable[Block],
    *,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> list[dict]:
    """Block 목록을 Chunk(dict) 목록으로 변환한다."""
    chunks: list[dict] = []
    buffer: list[str] = []
    buffer_len = 0
    current_path: list[str] = []
    current_page: int | None = None
    previous_text = ""

    def flush() -> None:
        nonlocal buffer, buffer_len, previous_text
        body = "\n".join(buffer).strip()
        if body:
            chunks.append(
                {
                    "chunk_index": len(chunks),
                    "page": current_page,
                    "section": _section_of(current_path),
                    "heading_path": " > ".join(current_path),
                    "text": _compose(current_path, body),
                }
            )
            previous_text = body
        buffer = []
        buffer_len = 0

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        # Section 변경 → 강제 분할
        if block.heading_path != current_path:
            flush()
            current_path = list(block.heading_path)
            current_page = block.page
            previous_text = ""

        if current_page is None:
            current_page = block.page

        if block.kind == "heading":
            # 제목은 heading_path 에 이미 반영되어 있으므로 본문 중복을 피한다.
            continue

        pieces = (
            _split_table(text, chunk_size)
            if block.kind == "table" and len(text) > chunk_size
            else [text]
        )

        for piece in pieces:
            # 문단 하나가 chunk_size 보다 크면 문장 단위로 잘라 넣는다.
            # (표는 _split_table 에서 이미 행 단위로 나뉘었으므로 그대로 둔다.)
            segments = (
                _split_long_paragraph(piece, chunk_size)
                if block.kind != "table" and len(piece) > chunk_size
                else [piece]
            )
            for segment in segments:
                if buffer and buffer_len + len(segment) > chunk_size:
                    flush()
                    # 표는 헤더 행이 반복되므로 overlap 을 붙이지 않는다.
                    overlap = (
                        "" if block.kind == "table" else _tail_overlap(previous_text, chunk_overlap)
                    )
                    if overlap:
                        buffer.append(overlap)
                        buffer_len += len(overlap)
                    current_page = block.page if block.page is not None else current_page
                buffer.append(segment)
                buffer_len += len(segment) + 1

    flush()

    # chunk_index 재정렬(플러시 순서대로 0..n-1)
    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
    return chunks


def _split_long_paragraph(text: str, chunk_size: int) -> list[str]:
    """긴 문단을 문장 경계 기준으로 나눈다."""
    import re

    sentences = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+|(?<=요\.)\s+", text)
    sentences = [sentence for sentence in sentences if sentence]
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > chunk_size:
            parts.append(current.strip())
            current = ""
        current += sentence + " "
        # 문장 자체가 지나치게 길면 강제로 자른다.
        while len(current) > chunk_size:
            parts.append(current[:chunk_size].strip())
            current = current[chunk_size:]
    if current.strip():
        parts.append(current.strip())
    return [part for part in parts if part]

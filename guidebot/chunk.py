"""문서 구조를 보존하는 Chunk 분할.

단순히 글자 수로 자르지 않고 제목 / Section 경계를 우선 사용한다.
각 Chunk에는 문서명, 페이지, Section, Chunk ID(=chunk_index)가 함께 저장된다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import Block
from .structure import detect_heading

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
MIN_CHUNK_LEN = 80  # 이보다 짧은 조각은 단독 chunk로 만들지 않는다


@dataclass
class ChunkData:
    """DB에 저장될 Chunk 한 개."""

    chunk_index: int
    text: str
    page_start: int
    page_end: int
    section: str = ""
    heading_path: str = ""
    extra: dict = field(default_factory=dict)

    def as_row(self) -> dict:
        return {
            "chunk_index": self.chunk_index,
            "text": self.text,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section": self.section,
            "heading_path": self.heading_path,
        }


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _split_long_text(text: str, limit: int) -> list[str]:
    """한 문단이 limit보다 길면 문장 단위로 나눈다."""
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _split_sentences(text):
        while len(sentence) > limit:  # 문장 하나가 limit를 넘는 극단적인 경우
            pieces.append(sentence[:limit])
            sentence = sentence[limit:]
        if not current:
            current = sentence
        elif len(current) + len(sentence) + 1 <= limit:
            current = f"{current} {sentence}"
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces


def _tail_overlap(text: str, overlap: int) -> str:
    """다음 chunk 앞에 붙일 겹침 텍스트(문장 경계 우선)를 만든다."""
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    sentences = _split_sentences(tail)
    if len(sentences) > 1:
        return " ".join(sentences[1:]).strip()
    return tail.strip()


def chunk_blocks(
    blocks: list[Block],
    *,
    chunk_size: int = 900,
    overlap: int = 150,
    doc_title: str = "",
) -> list[ChunkData]:
    """추출된 Block 목록을 구조 기반 Chunk로 변환한다."""
    if chunk_size <= 0:
        raise ValueError("chunk_size는 1 이상이어야 합니다.")
    overlap = max(0, min(overlap, chunk_size // 2))

    chunks: list[ChunkData] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[tuple[str, int]] = []        # 현재 Section에 쌓이는 (text, page)
    carry_buffer: list[tuple[str, int]] = []  # 다음 Section으로 넘길 짧은 조각

    def heading_path() -> str:
        parts = [doc_title] if doc_title else []
        parts.extend(title for _, title in heading_stack)
        return " > ".join(parts)

    def section_name() -> str:
        return heading_stack[-1][1] if heading_stack else ""

    def flush(final: bool = False) -> None:
        if not buffer:
            return
        # 제목만 남은 매우 짧은 조각은 독립 chunk로 만들지 않고 다음 Section에 붙인다.
        combined_len = sum(len(t) for t, _ in buffer)
        if not final and combined_len < MIN_CHUNK_LEN:
            carry_buffer.extend(buffer)
            buffer.clear()
            return
        path, section = heading_path(), section_name()
        units: list[tuple[str, int]] = []
        pending = carry_buffer + list(buffer)
        carry_buffer.clear()
        for text, page in pending:
            for piece in _split_long_text(text, chunk_size):
                units.append((piece, page))

        current_text = ""
        pages: list[int] = []
        for text, page in units:
            candidate = f"{current_text}\n{text}".strip() if current_text else text
            too_long = len(candidate) > chunk_size
            if current_text and too_long and len(current_text) >= MIN_CHUNK_LEN:
                chunks.append(
                    ChunkData(
                        chunk_index=len(chunks),
                        text=current_text.strip(),
                        page_start=min(pages),
                        page_end=max(pages),
                        section=section,
                        heading_path=path,
                    )
                )
                carry = _tail_overlap(current_text, overlap)
                current_text = f"{carry}\n{text}".strip() if carry else text
                pages = [page]
            else:
                current_text = candidate
                pages.append(page)
        if current_text.strip():
            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    text=current_text.strip(),
                    page_start=min(pages) if pages else 1,
                    page_end=max(pages) if pages else 1,
                    section=section,
                    heading_path=path,
                )
            )
        buffer.clear()

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        is_heading, level = (block.kind == "heading"), block.level or 1
        if not is_heading and block.kind == "body":
            detected, detected_level, detected_text = detect_heading(text)
            if detected:
                is_heading, level, text = True, detected_level, detected_text

        if is_heading:
            flush()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
            # 제목 자체도 문맥으로 남긴다(짧은 Section 검색에 도움).
            buffer.append((text, block.page))
        else:
            buffer.append((text, block.page))

    flush(final=True)
    if carry_buffer:  # 마지막까지 남은 짧은 조각도 버리지 않는다.
        buffer.extend(carry_buffer)
        carry_buffer.clear()
        flush(final=True)
    return chunks


def build_embedding_text(chunk: ChunkData | dict, doc_title: str = "", version: str = "") -> str:
    """Embedding에 사용할 텍스트(구조 정보 포함)를 만든다."""
    if isinstance(chunk, ChunkData):
        heading_path, text, section = chunk.heading_path, chunk.text, chunk.section
    else:
        heading_path = chunk.get("heading_path", "")
        text = chunk.get("text", "")
        section = chunk.get("section", "")
    header_parts = [p for p in (doc_title, version and f"v{version}", heading_path or section) if p]
    header = " | ".join(header_parts)
    return f"{header}\n{text}".strip() if header else text

"""Chunking 구조 보존 테스트 (요구사항 8)."""

from app.chunker import chunk_blocks
from app.extractors import Block, detect_heading


def test_detect_heading_patterns():
    assert detect_heading("5.3 Encryption Rule") == "5.3 Encryption Rule"
    assert detect_heading("제 3 장 데이터 관리") is not None
    assert detect_heading("## 목적") == "목적"
    assert detect_heading("본 문서는 절차를 정의한다.") is None


def test_section_change_forces_new_chunk():
    blocks = [
        Block(text="첫 번째 섹션 내용", page=1, heading_path=["5. Data Transfer"]),
        Block(text="두 번째 섹션 내용", page=2, heading_path=["6. 승인"]),
    ]
    chunks = chunk_blocks(blocks, chunk_size=900, chunk_overlap=100)
    assert len(chunks) == 2
    assert chunks[0]["section"] == "5. Data Transfer"
    assert chunks[0]["page"] == 1
    assert chunks[1]["section"] == "6. 승인"
    assert chunks[1]["page"] == 2
    assert chunks[0]["chunk_index"] == 0 and chunks[1]["chunk_index"] == 1


def test_heading_path_is_prefixed_to_text():
    blocks = [Block(text="본문", page=3, heading_path=["5. Transfer", "5.3 Encryption"])]
    chunks = chunk_blocks(blocks)
    assert chunks[0]["heading_path"] == "5. Transfer > 5.3 Encryption"
    assert chunks[0]["text"].startswith("[문서 위치] 5. Transfer > 5.3 Encryption")
    assert "본문" in chunks[0]["text"]


def test_long_section_is_split_with_overlap():
    body = " ".join(f"문장{i}번 입니다." for i in range(200))
    blocks = [Block(text=body, page=1, heading_path=["1. 개요"])]
    chunks = chunk_blocks(blocks, chunk_size=300, chunk_overlap=60)
    assert len(chunks) > 1
    assert all(chunk["section"] == "1. 개요" for chunk in chunks)
    # 모든 chunk 가 chunk_size + overlap + 머리말 여유 범위 안에 있어야 한다.
    assert all(len(chunk["text"]) < 300 + 60 + 120 for chunk in chunks)


def test_heading_block_is_not_duplicated_in_body():
    blocks = [
        Block(text="5.3 Encryption", page=1, kind="heading", heading_path=["5.3 Encryption"]),
        Block(text="파일은 암호화한다.", page=1, heading_path=["5.3 Encryption"]),
    ]
    chunks = chunk_blocks(blocks)
    assert len(chunks) == 1
    assert chunks[0]["text"].count("5.3 Encryption") == 1


def test_large_table_repeats_header_row():
    rows = ["항목 | 담당자 | 기한"] + [f"항목{i} | 담당{i} | D+{i}" for i in range(100)]
    blocks = [Block(text="\n".join(rows), page=2, kind="table", heading_path=["별첨"])]
    chunks = chunk_blocks(blocks, chunk_size=300, chunk_overlap=0)
    assert len(chunks) > 1
    assert all("항목 | 담당자 | 기한" in chunk["text"] for chunk in chunks)

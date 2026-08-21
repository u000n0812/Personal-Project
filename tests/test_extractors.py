"""문서 형식별 텍스트 추출 테스트 (요구사항 5 / Phase 2)."""

from pathlib import Path

import pytest

from app.extractors import UnsupportedDocument, extract

docx = pytest.importorskip("docx", reason="python-docx 미설치")
openpyxl = pytest.importorskip("openpyxl", reason="openpyxl 미설치")


def test_txt_extraction_keeps_headings(tmp_path: Path):
    path = tmp_path / "guide.txt"
    path.write_text(
        "1. 목적\n본 문서는 절차를 정의한다.\n\n5.3 Encryption Rule\n파일은 암호화한다.\n",
        encoding="utf-8",
    )
    result = extract(path)
    headings = [block.text for block in result.blocks if block.kind == "heading"]
    assert "1. 목적" in headings
    assert "5.3 Encryption Rule" in headings
    body = [block for block in result.blocks if block.kind == "paragraph"]
    assert any("암호화" in block.text for block in body)
    assert all(block.page == 1 for block in result.blocks)


def test_txt_extraction_supports_cp949(tmp_path: Path):
    path = tmp_path / "cp949.txt"
    path.write_bytes(
        "1. 목적\n한글 인코딩 확인용 문서입니다. 사내 지침문서는 cp949 로 저장된 경우가 있다.\n".encode(
            "cp949"
        )
    )
    result = extract(path)
    assert any("한글 인코딩" in block.text for block in result.blocks)


def test_docx_extraction_keeps_heading_hierarchy(tmp_path: Path):
    document = docx.Document()
    document.add_heading("Data Transfer Specification", level=1)
    document.add_heading("5. Data Transfer", level=1)
    document.add_heading("5.3 Encryption Rule", level=2)
    document.add_paragraph("Password 는 별도의 Email 로 전달한다.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "항목"
    table.cell(0, 1).text = "담당자"
    table.cell(1, 0).text = "암호화"
    table.cell(1, 1).text = "Data Provider"
    path = tmp_path / "spec.docx"
    document.save(path)

    result = extract(path)
    paragraph = next(block for block in result.blocks if "Password" in block.text and block.kind == "paragraph")
    assert paragraph.heading_path[-1] == "5.3 Encryption Rule"
    assert any(block.kind == "table" and "담당자" in block.text for block in result.blocks)


def test_xlsx_extraction_uses_sheet_as_section(tmp_path: Path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "전달 이력"
    sheet.append(["일자", "파일명", "담당자"])
    sheet.append(["2024-03-15", "ABC123_LAB_20240315_v1", "홍길동"])
    path = tmp_path / "history.xlsx"
    workbook.save(path)

    result = extract(path)
    assert any("[Sheet] 전달 이력" in " > ".join(block.heading_path) for block in result.blocks)
    assert any("ABC123_LAB" in block.text for block in result.blocks)


def test_empty_document_is_rejected_as_scanned(tmp_path: Path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n\n", encoding="utf-8")
    with pytest.raises(UnsupportedDocument):
        extract(path)


def test_unsupported_extension_is_rejected(tmp_path: Path):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(UnsupportedDocument):
        extract(path)


def test_pdf_extraction_reports_pages(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf", reason="pypdf 미설치")
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    with open(path, "wb") as handle:
        writer.write(handle)

    # 텍스트가 없는(스캔으로 간주되는) PDF 는 등록을 거부한다.
    with pytest.raises(UnsupportedDocument):
        extract(path)

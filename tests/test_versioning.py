"""문서 버전 인식 테스트 (요구사항 7)."""

import pytest

from app.versioning import doc_key_of, parse_version, version_sort_key


@pytest.mark.parametrize(
    "filename, base, version",
    [
        ("SOP_DataManagement_v1.0.pdf", "SOP_DataManagement", "1.0"),
        ("SOP_DataManagement_v2.0.docx", "SOP_DataManagement", "2.0"),
        ("SOP DataManagement v1.1.txt", "SOP DataManagement", "1.1"),
        ("Data Transfer Spec (v2.1).pdf", "Data Transfer Spec", "2.1"),
        ("Guideline_rev3.pdf", "Guideline", "3"),
        ("업무절차서_20240131.pdf", "업무절차서", "20240131"),
        ("버전없는문서.pdf", "버전없는문서", ""),
    ],
)
def test_parse_version(filename, base, version):
    assert parse_version(filename) == (base, version)


def test_same_document_different_versions_share_doc_key():
    keys = {
        doc_key_of("SOP_DataManagement_v1.0.pdf"),
        doc_key_of("SOP_DataManagement_v1.1.pdf"),
        doc_key_of("SOP DataManagement v2.0.docx"),
    }
    assert len(keys) == 1


def test_version_sort_key_orders_numerically():
    assert version_sort_key("1.10") > version_sort_key("1.9")
    assert version_sort_key("2.0") > version_sort_key("1.10")
    assert version_sort_key("1.0") > version_sort_key("")

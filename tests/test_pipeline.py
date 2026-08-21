"""문서 등록/버전/삭제 파이프라인 테스트 (요구사항 6, 7, 18, 20)."""

from pathlib import Path

from app import db
from app.config import DOCUMENTS_DIR
from app.search import search


def test_ingest_creates_chunks_and_vectors(index, sample_dir):
    results = index.ingest_folder(sample_dir)
    assert len(results) == 2
    assert all(result.status == "indexed" for result in results), [r.message for r in results]
    assert all(result.chunk_count > 0 for result in results)

    info = index.stats()
    assert info["documents"] == 2
    assert info["chunks"] == info["vectors"] > 0

    # 원본 파일이 data/documents 에 보관된다.
    assert len(list(Path(DOCUMENTS_DIR).glob("*.txt"))) == 2


def test_metadata_contains_page_and_section(index, sample_dir):
    index.ingest_folder(sample_dir)
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM chunks").fetchall()
    assert rows
    assert any(row["heading_path"] for row in rows)
    assert all(row["page"] is not None for row in rows)


def test_duplicate_ingest_is_skipped(index, sample_dir):
    index.ingest_folder(sample_dir)
    before = index.stats()["chunks"]
    results = index.ingest_folder(sample_dir)
    assert all(result.status == "skipped" for result in results)
    assert index.stats()["chunks"] == before  # 재임베딩하지 않는다(요구사항 20)


def test_new_version_deactivates_old_version(index, sample_dir, tmp_path):
    index.ingest_file(sample_dir / "Database_Lock_Guideline_v1.4.txt")
    new_version = tmp_path / "Database_Lock_Guideline_v2.0.txt"
    new_version.write_text(
        (sample_dir / "Database_Lock_Guideline_v1.4.txt").read_text(encoding="utf-8")
        + "\n5. 추가 항목\nDB Lock 후 데이터 변경은 금지한다.\n",
        encoding="utf-8",
    )
    index.ingest_file(new_version)

    rows = {row["version"]: row["status"] for row in index.documents()}
    assert rows["1.4"] == "inactive"
    assert rows["2.0"] == "active"


def test_same_version_with_changed_content_is_replaced(index, sample_dir, tmp_path):
    original = sample_dir / "Database_Lock_Guideline_v1.4.txt"
    index.ingest_file(original)
    changed = tmp_path / "Database_Lock_Guideline_v1.4.txt"
    changed.write_text(
        original.read_text(encoding="utf-8") + "\n6. 개정\n내용이 변경되었다.\n",
        encoding="utf-8",
    )
    result = index.ingest_file(changed)
    assert result.status == "replaced"
    assert len(index.documents()) == 1


def test_delete_removes_file_chunks_and_vectors(index, sample_dir):
    index.ingest_folder(sample_dir)
    document_id = int(index.documents()[0]["id"])
    with db.connect() as conn:
        stored_path = Path(db.get_document(conn, document_id)["stored_path"])
    assert stored_path.exists()

    assert index.delete_document(document_id) is True

    with db.connect() as conn:
        assert db.get_document(conn, document_id) is None
        remaining = conn.execute(
            "SELECT COUNT(*) AS c FROM chunks WHERE document_id = ?", (document_id,)
        ).fetchone()["c"]
    assert remaining == 0
    assert not stored_path.exists()
    assert index.stats()["chunks"] == index.stats()["vectors"]


def test_reindex_keeps_document_and_refreshes_chunks(index, sample_dir):
    index.ingest_folder(sample_dir)
    document_id = int(index.documents()[0]["id"])
    result = index.reindex_document(document_id)
    assert result.status == "indexed"
    assert result.chunk_count > 0
    assert index.stats()["chunks"] == index.stats()["vectors"]


def test_index_persists_across_restart(index, sample_dir, settings):
    from app.pipeline import DocumentIndex

    index.ingest_folder(sample_dir)
    expected = index.stats()

    # 프로그램을 다시 실행한 상황을 흉내낸다.
    reopened = DocumentIndex(settings)
    assert reopened.stats()["vectors"] == expected["vectors"]
    assert search(reopened, "Password 전달", settings).has_results


def test_inactive_document_is_excluded_from_search(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    for row in index.documents():
        index.set_status(int(row["id"]), active=False)
    assert not search(index, "Password 전달", settings).has_results

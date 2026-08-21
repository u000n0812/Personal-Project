"""검색 품질 테스트 (요구사항 9 / Phase 4)."""

from app.search import search


def test_finds_encryption_rule_document(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    result = search(index, "파일을 Vendor에게 전달할 때 암호화 규칙이 어떻게 돼?", settings)
    assert result.has_results
    assert "External" in result.hits[0].title
    assert "암호화" in result.hits[0].body or "Password" in result.hits[0].body


def test_finds_db_lock_checklist(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    result = search(index, "DB Lock 전에 확인해야 하는 항목이 뭐였지?", settings)
    assert result.has_results
    assert "Database Lock" in result.hits[0].title


def test_abbreviation_dbl_matches_database_lock(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    result = search(index, "DBL 확인 항목", settings)
    assert result.has_results
    assert "Database Lock" in result.hits[0].title


def test_hit_citation_contains_document_version_and_page(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    hit = search(index, "Password 전달 방법", settings).hits[0]
    assert hit.version
    assert "v" in hit.citation
    assert "Page" in hit.citation


def test_unrelated_question_returns_no_strong_hit(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    settings.score_threshold = 0.6
    result = search(index, "구내식당 점심 메뉴 신청은 어떻게 해?", settings)
    assert not result.has_results


def test_empty_query_returns_nothing(index, settings):
    assert not search(index, "   ", settings).has_results

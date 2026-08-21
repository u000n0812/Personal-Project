"""BM25 키워드 검색과 동의어 확장 테스트 (요구사항 9)."""

from app.keyword import BM25Index
from app.text_utils import expand_query, tokenize


def test_tokenizer_generates_korean_ngrams():
    tokens = tokenize("전달 절차가")
    assert "절차가" in tokens
    assert "절차" in tokens  # 2-gram 으로 조사 변형 흡수


def test_bm25_ranks_relevant_chunk_first():
    index = BM25Index().build(
        [
            (1, "Password 는 별도의 Email 로 전달한다."),
            (2, "본 문서는 임상시험 자료 관리 절차를 정의한다."),
            (3, "DB Lock 전에 Query 종결 여부를 확인한다."),
        ]
    )
    results = index.search("Password 전달 방법")
    assert results and results[0][0] == 1


def test_synonym_expansion_bridges_abbreviations():
    index = BM25Index().build(
        [
            (1, "Database Lock 전에 모든 Query 를 종결한다."),
            (2, "External Data 전달 시 파일을 암호화한다."),
        ]
    )
    assert index.search("DBL 확인 항목") == [] or index.search("DBL 확인 항목")[0][0] != 1
    expanded = expand_query("DBL 확인 항목")
    results = index.search(expanded)
    assert results and results[0][0] == 1


def test_empty_index_returns_empty():
    assert BM25Index().search("아무거나") == []

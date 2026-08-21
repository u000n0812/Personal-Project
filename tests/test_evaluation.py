"""질문 세트 기반 검색 품질 회귀 테스트 (Phase 10).

docs/test_questions.json 의 22개 근거 질문이 모두 정답 문서를 Top-3 안에
검색하는지 확인한다. (문서에 없는 질문에 대한 최종 거부는 답변 단계에서
LLM 이 담당하며 tests/test_rag.py 에서 별도로 검증한다.)
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"

import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import evaluate as evaluator  # noqa: E402


def test_sample_questions_are_retrieved(index, settings):
    results = index.ingest_folder(SAMPLES)
    assert all(result.ok for result in results), [r.message for r in results]

    documents, questions = evaluator.load_questions()
    report = evaluator.evaluate(index, settings, documents, questions, top_k=3)

    failures = [row["question"] for row in report["rows"] if not row["passed"] and row["expect"] != "none"]
    assert report["retrieval_accuracy"] == 1.0, f"검색 실패: {failures}"
    # 문서에 없는 질문 중 최소 절반은 검색 단계에서 걸러져야 한다.
    assert report["rejection_accuracy"] >= 0.5


def test_question_set_covers_at_least_20_cases():
    _, questions = evaluator.load_questions()
    assert len(questions) >= 20
    assert sum(1 for item in questions if item["expect"] == "none") >= 3

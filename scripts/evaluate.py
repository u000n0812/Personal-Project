"""검색 품질 평가 (Phase 4 / Phase 10).

docs/test_questions.json 의 질문 세트로 검색 정확도를 측정한다.
LLM 없이 검색만 평가하므로 Ollama 가 없어도 실행할 수 있다.

    python scripts/evaluate.py                 # samples/ 문서로 평가
    python scripts/evaluate.py --docs "C:/회사지침"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUESTION_FILE = ROOT / "docs" / "test_questions.json"


def load_questions(path: Path = QUESTION_FILE) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["documents"], payload["questions"]


def evaluate(index, settings, documents: dict, questions: list[dict], top_k: int = 3) -> dict:
    """질문별 검색 결과를 채점한다."""
    from app.search import search

    rows = []
    for item in questions:
        result = search(index, item["question"], settings)
        hits = result.hits[:top_k]
        titles = [hit.title.lower() for hit in hits]

        if item["expect"] == "none":
            passed = not result.hits
            found = titles[0] if titles else "-"
        else:
            expected_title = documents[item["expect"]].lower()
            passed = any(expected_title in title or title in expected_title for title in titles)
            found = titles[0] if titles else "-"

        rows.append(
            {
                "question": item["question"],
                "expect": item["expect"],
                "passed": passed,
                "found": found,
                "top_score": round(hits[0].score, 3) if hits else 0.0,
                "citation": hits[0].citation if hits else "",
            }
        )

    grounded = [row for row in rows if row["expect"] != "none"]
    rejected = [row for row in rows if row["expect"] == "none"]
    return {
        "rows": rows,
        "total": len(rows),
        "passed": sum(1 for row in rows if row["passed"]),
        "retrieval_accuracy": (
            sum(1 for row in grounded if row["passed"]) / len(grounded) if grounded else 0.0
        ),
        "rejection_accuracy": (
            sum(1 for row in rejected if row["passed"]) / len(rejected) if rejected else 0.0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="검색 품질 평가")
    parser.add_argument("--docs", default=str(ROOT / "samples"), help="평가에 사용할 문서 폴더")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=None, help="검색 threshold 재정의")
    parser.add_argument(
        "--reuse-data", action="store_true", help="임시 폴더 대신 실제 data/ 인덱스를 사용"
    )
    parser.add_argument(
        "--strict", action="store_true", help="거부 정확도까지 100% 여야 통과로 판정"
    )
    args = parser.parse_args()

    if not args.reuse_data:
        os.environ["CHATBOT_DATA_DIR"] = tempfile.mkdtemp(prefix="chatbot-eval-")

    from app import netguard

    netguard.install()

    from app.config import load_settings
    from app.pipeline import DocumentIndex

    settings = load_settings()
    if args.threshold is not None:
        settings.score_threshold = args.threshold

    index = DocumentIndex(settings)
    if not args.reuse_data:
        results = index.ingest_folder(args.docs)
        failed = [result for result in results if not result.ok]
        if failed:
            for result in failed:
                print(f"[등록 실패] {result.filename}: {result.message}")
            return 1
        print(f"평가용 문서 {len(results)}건 등록 완료\n")

    documents, questions = load_questions()
    report = evaluate(index, settings, documents, questions, top_k=args.top_k)

    print(f"{'결과':<5} {'기대':<9} {'점수':>6}  질문 / 검색된 문서")
    print("-" * 92)
    for row in report["rows"]:
        mark = "PASS " if row["passed"] else "FAIL "
        print(f"{mark:<5} {row['expect']:<9} {row['top_score']:>6}  {row['question']}")
        print(f"{'':<22}→ {row['citation'] or '검색 결과 없음'}")

    print("-" * 92)
    print(f"전체 통과      : {report['passed']}/{report['total']}")
    print(f"검색 정확도     : {report['retrieval_accuracy']:.0%}  (Top-{args.top_k} 안에 정답 문서)")
    print(f"거부 정확도     : {report['rejection_accuracy']:.0%}  (문서에 없는 질문을 검색 단계에서 거부)")
    print()
    print("참고: 검색 단계에서 걸러지지 않은 질문도 답변 단계에서 한 번 더 차단된다.")
    print("      (LLM 은 참고 문서에 근거가 없으면 '등록된 지침문서에서는 ...' 로만 답하도록 강제된다.)")
    print("      거부 정확도가 낮으면 --threshold 값을 올려 재측정하세요.")

    if args.strict:
        return 0 if report["passed"] == report["total"] else 1
    return 0 if report["retrieval_accuracy"] >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())

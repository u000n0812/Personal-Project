#!/usr/bin/env python3
"""지침문서 어시스턴트 명령줄 도구.

UI 없이 각 단계(Phase)를 점검하거나 문서를 일괄 등록할 때 사용한다.

사용 예:
    python cli.py doctor
    python cli.py add ./sample_docs
    python cli.py list
    python cli.py search "DB Lock 전에 확인할 항목"
    python cli.py ask "External Data 전달 절차 알려줘"
    python cli.py selfcheck
    python cli.py backup
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sopbot import backup as backup_module  # noqa: E402
from sopbot.config import DATA_DIR, Settings  # noqa: E402
from sopbot.db import STATUS_ACTIVE, STATUS_DISABLED  # noqa: E402
from sopbot.security import scan_source_tree  # noqa: E402
from sopbot.service import AppService  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent


def _service(warn: bool = True) -> AppService:
    service = AppService(Settings.load())
    if warn and service.ingestor.embedding_model_changed():
        print(
            f"[경고] Vector Index는 '{service.store.embedder_name}' 로 만들어졌지만 "
            f"현재 '{service.embedder.name}' 가 사용 중입니다.\n"
            "        Ollama 실행 여부를 확인하거나 `python cli.py rebuild` 를 실행하세요.\n"
        )
    return service


# ---------------------------------------------------------------------------
def cmd_doctor(args: argparse.Namespace) -> int:
    service = _service()
    print("=== 실행 환경 점검 ===")
    for line in service.health().as_lines():
        print(" ", line)
    problems = scan_source_tree(PROJECT_ROOT)
    print("\n=== 외부 통신 코드 점검 ===")
    if problems:
        for problem in problems:
            print("  [경고]", problem)
        return 1
    print("  외부 API / 외부 URL 사용 없음 (로컬 전용)")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    service = _service()
    results = service.register(args.paths)
    if not results:
        print("등록할 문서를 찾지 못했습니다.")
        return 1
    failed = 0
    for result in results:
        mark = "OK " if result.ok else ("-- " if result.status in ("duplicate", "skipped") else "ERR")
        if result.status == "error":
            failed += 1
        print(f"{mark} {result.file_name}: {result.message} (chunk {result.chunk_count})")
    print(f"\n완료: 총 {len(results)}건, 실패 {failed}건")
    return 1 if failed else 0


def cmd_list(args: argparse.Namespace) -> int:
    service = _service()
    documents = service.documents(include_all=True)
    if not documents:
        print("등록된 문서가 없습니다. `python cli.py add <경로>` 로 등록하세요.")
        return 0
    print(f"{'ID':>4}  {'상태':<11} {'버전':<6} {'Chunk':>6}  문서명")
    print("-" * 78)
    for document in documents:
        print(
            f"{document.id:>4}  {document.status:<11} {document.version:<6} "
            f"{document.chunk_count:>6}  {document.title} ({document.file_name})"
        )
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    service = _service()
    document = service.db.get_document(args.document_id)
    if document is None:
        print("문서를 찾을 수 없습니다.")
        return 1
    if not args.yes:
        answer = input(f"'{document.title}' 문서를 완전히 삭제할까요? (y/N) ").strip().lower()
        if answer != "y":
            print("취소했습니다.")
            return 0
    result = service.ingestor.delete(args.document_id)
    service.retriever.invalidate()
    print(result.message)
    return 0 if result.ok else 1


def cmd_reindex(args: argparse.Namespace) -> int:
    service = _service()
    result = service.ingestor.reindex(args.document_id)
    service.retriever.invalidate()
    print(f"{result.file_name}: {result.message} (chunk {result.chunk_count})")
    return 0 if result.ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    service = _service()
    status = STATUS_DISABLED if args.command == "disable" else STATUS_ACTIVE
    result = service.ingestor.set_status(args.document_id, status)
    service.retriever.invalidate()
    print(result.message)
    return 0 if result.ok else 1


def cmd_search(args: argparse.Namespace) -> int:
    service = _service()
    results = service.retriever.search(args.query, top_k=args.k)
    if not results:
        print("검색 결과가 없습니다.")
        return 0
    for index, result in enumerate(results, start=1):
        print(f"\n[{index}] {result.citation}")
        print(f"    점수 {result.score:.3f} (vector {result.vector_score:.3f} / keyword {result.keyword_score:.2f})")
        preview = result.chunk.text.replace("\n", " ")
        print(f"    {preview[:200]}{'...' if len(preview) > 200 else ''}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    service = _service()
    answer = service.ask(args.question)
    print(answer.answer)
    print(f"\n(검색 {len(answer.results)}건, LLM 사용 {'예' if answer.used_llm else '아니오'}, {answer.elapsed_sec}s)")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    service = _service()
    count = service.ingestor.rebuild_index()
    service.retriever.invalidate()
    print(f"Vector Index를 다시 만들었습니다: chunk {count}개")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    path = backup_module.create_backup(args.out)
    print(f"백업 생성: {path}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    if not args.yes:
        answer = input("현재 data 폴더 내용을 덮어씁니다. 계속할까요? (y/N) ").strip().lower()
        if answer != "y":
            print("취소했습니다.")
            return 0
    count = backup_module.restore_backup(args.archive)
    print(f"복원 완료: {count}개 파일")
    return 0


def cmd_selfcheck(args: argparse.Namespace) -> int:
    problems = scan_source_tree(PROJECT_ROOT)
    print("=== 소스코드 외부 통신 점검 ===")
    if problems:
        for problem in problems:
            print("  [경고]", problem)
        print("\n외부 통신 흔적이 발견되었습니다.")
        return 1
    print("  통과: 외부 AI API / 외부 URL / telemetry 코드 없음")
    print(f"  데이터 저장 위치: {DATA_DIR}")
    return 0


# 관련 문장 / 무관한 문장 쌍으로 Embedding 모델의 분별력을 확인한다.
EMBED_PROBES = [
    (
        "DB Lock 전에 확인해야 하는 항목이 뭐야?",
        "Database Lock 이전에 미해결 Query가 0건인지 확인하고 SAE Reconciliation 완료 여부를 확인한다.",
        "법인카드 사용 한도는 부서장 승인 후 월 200만원까지 인정된다.",
    ),
    (
        "외부에 파일 보낼 때 암호화 규칙이 어떻게 돼?",
        "전달 파일은 AES-256으로 암호화하고 Password는 별도의 Email로 전달한다.",
        "구내식당 점심 운영 시간은 11시 30분부터 13시까지이다.",
    ),
    (
        "이 업무는 누구에게 승인을 받아야 해?",
        "최종 승인은 Project Manager가 수행하며 승인 없이 진행할 수 없다.",
        "연차 휴가는 사용 3일 전까지 신청한다.",
    ),
    (
        "지침문서 교육은 언제까지 받아야 해?",
        "개정 문서는 효력 발생일로부터 30일 이내에 담당자 교육을 실시한다.",
        "주차 등록은 총무팀에 차량 번호를 제출하면 된다.",
    ),
    (
        "DBL 승인 절차 알려줘",
        "DB Lock 체크리스트는 Data Manager가 작성하고 Project Manager가 최종 승인한다.",
        "사내 동호회 지원금은 반기별로 지급된다.",
    ),
]


def cmd_embed_check(args: argparse.Namespace) -> int:
    """Embedding 모델이 관련 문장과 무관한 문장을 구분하는지 확인한다."""
    service = _service(warn=False)
    embedder = service.embedder
    print(f"Embedding backend : {embedder.name} (dim={embedder.dimension})")
    if embedder.name.startswith("hashing"):
        print("[경고] 모델을 찾지 못해 fallback(hashing)이 사용 중입니다.")
        print("       Ollama 실행 여부와 `ollama pull bge-m3` 설치를 확인하세요.\n")

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b))

    related_scores, unrelated_scores = [], []
    print(f"\n{'질문':38} {'관련 문장':>9} {'무관 문장':>9} {'차이':>7}")
    print("-" * 70)
    for question, related, unrelated in EMBED_PROBES:
        query_vector = embedder.encode_query(question)
        related_vector, unrelated_vector = embedder.encode_documents([related, unrelated])
        related_score = cosine(query_vector, related_vector)
        unrelated_score = cosine(query_vector, unrelated_vector)
        related_scores.append(related_score)
        unrelated_scores.append(unrelated_score)
        display = question if len(question) <= 36 else question[:35] + "…"
        print(f"{display:38} {related_score:>9.3f} {unrelated_score:>9.3f} {related_score - unrelated_score:>7.3f}")

    mean_related = sum(related_scores) / len(related_scores)
    mean_unrelated = sum(unrelated_scores) / len(unrelated_scores)
    gap = mean_related - mean_unrelated
    print("-" * 70)
    print(f"{'평균':38} {mean_related:>9.3f} {mean_unrelated:>9.3f} {gap:>7.3f}")

    recommended = round(((mean_related + mean_unrelated) / 2) * 20) / 20  # 0.05 단위
    recommended = max(0.05, min(0.9, recommended))
    print(f"\n현재 적용 threshold : {service.retriever.effective_threshold:.2f}")
    print(f"이 모델 권장값      : {recommended:.2f}")
    if gap < 0.08:
        print("\n[경고] 관련 문장과 무관한 문장의 점수 차이가 너무 작습니다.")
        print("       Embedding 모델 설정을 확인하세요(권장: Ollama bge-m3).")
        return 1
    print("\n권장값을 쓰려면 Settings에서 threshold를 직접 입력하거나,")
    print("0(자동)으로 두면 모델별 기본값이 적용됩니다.")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """질문 목록으로 검색 품질을 일괄 점검한다(Phase 10)."""
    path = Path(args.file)
    if not path.exists():
        print(f"질문 파일을 찾을 수 없습니다: {path}")
        return 1
    cases = json.loads(path.read_text(encoding="utf-8"))
    service = _service()
    passed = 0
    for case in cases:
        question = case["question"]
        expect = case.get("expect_doc", "")
        results = service.retriever.search(question, top_k=args.k)
        top_titles = [r.document.title for r in results]
        hit = (not expect and not results) or any(expect.lower() in t.lower() for t in top_titles)
        if case.get("expect_none"):
            hit = not service.retriever.has_sufficient_evidence(results, question)
        passed += 1 if hit else 0
        mark = "PASS" if hit else "FAIL"
        print(f"[{mark}] {question}")
        if not hit:
            print(f"       기대: {expect or '근거 없음'} / 실제: {top_titles[:3]}")
    print(f"\n검색 정확도: {passed}/{len(cases)}")
    return 0 if passed == len(cases) else 1


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py", description="사내 지침문서 Local RAG 어시스턴트 (완전 로컬 실행)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="실행 환경 및 보안 점검").set_defaults(func=cmd_doctor)

    add_parser = sub.add_parser("add", help="문서/폴더 등록")
    add_parser.add_argument("paths", nargs="+", help="파일 또는 폴더 경로")
    add_parser.set_defaults(func=cmd_add)

    sub.add_parser("list", help="등록된 문서 목록").set_defaults(func=cmd_list)

    remove_parser = sub.add_parser("remove", help="문서 완전 삭제")
    remove_parser.add_argument("document_id", type=int)
    remove_parser.add_argument("--yes", action="store_true", help="확인 없이 삭제")
    remove_parser.set_defaults(func=cmd_remove)

    reindex_parser = sub.add_parser("reindex", help="문서 재색인")
    reindex_parser.add_argument("document_id", type=int)
    reindex_parser.set_defaults(func=cmd_reindex)

    for name, help_text in (("disable", "문서 비활성화"), ("enable", "문서 활성화")):
        status_parser = sub.add_parser(name, help=help_text)
        status_parser.add_argument("document_id", type=int)
        status_parser.set_defaults(func=cmd_status)

    search_parser = sub.add_parser("search", help="검색 결과만 확인 (LLM 미사용)")
    search_parser.add_argument("query")
    search_parser.add_argument("-k", type=int, default=5, help="결과 수 (기본 5)")
    search_parser.set_defaults(func=cmd_search)

    ask_parser = sub.add_parser("ask", help="질문하고 답변 받기 (로컬 LLM 사용)")
    ask_parser.add_argument("question")
    ask_parser.set_defaults(func=cmd_ask)

    sub.add_parser("rebuild", help="Vector Index 전체 재생성").set_defaults(func=cmd_rebuild)

    backup_parser = sub.add_parser("backup", help="data 폴더 백업(zip)")
    backup_parser.add_argument("--out", default=None, help="백업 폴더 (기본 backup/)")
    backup_parser.set_defaults(func=cmd_backup)

    restore_parser = sub.add_parser("restore", help="백업 zip 복원")
    restore_parser.add_argument("archive")
    restore_parser.add_argument("--yes", action="store_true")
    restore_parser.set_defaults(func=cmd_restore)

    sub.add_parser("selfcheck", help="외부 통신 코드 점검").set_defaults(func=cmd_selfcheck)

    sub.add_parser(
        "embed-check", help="Embedding 모델 분별력 점검 및 threshold 권장값 확인"
    ).set_defaults(func=cmd_embed_check)

    eval_parser = sub.add_parser("eval", help="질문 목록으로 검색 품질 점검")
    eval_parser.add_argument("--file", default="sample_docs/eval_questions.json")
    eval_parser.add_argument("-k", type=int, default=5)
    eval_parser.set_defaults(func=cmd_eval)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

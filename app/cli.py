"""명령줄 도구 (UI 없이 각 Phase 를 점검할 때 사용).

예)
  python -m app.cli doctor
  python -m app.cli add "C:/지침/SOP_DataManagement_v2.0.pdf"
  python -m app.cli addfolder "C:/지침"
  python -m app.cli list
  python -m app.cli search "External Data 전달 절차"
  python -m app.cli ask "DB Lock 전에 확인해야 하는 항목이 뭐야?"
  python -m app.cli backup
"""

from __future__ import annotations

import argparse
import sys

from app import netguard

netguard.install()  # 외부 통신 차단을 가장 먼저 설치한다.

from app.backup import create_backup, list_backups  # noqa: E402
from app.config import DATA_DIR, load_settings, save_settings  # noqa: E402
from app.llm import LocalLLMError, OllamaClient  # noqa: E402
from app.pipeline import DocumentIndex  # noqa: E402
from app.rag import RagEngine  # noqa: E402
from app.search import search  # noqa: E402


def cmd_doctor(args) -> int:
    settings = load_settings()
    print("=== 로컬 환경 점검 ===")
    print(f"- 데이터 폴더        : {DATA_DIR}")
    print(f"- 외부 네트워크 차단 : {'ON' if netguard.is_installed() else 'OFF'}")

    client = OllamaClient(settings.ollama_host)
    if client.health():
        models = client.list_models()
        print(f"- Ollama             : 정상 ({settings.ollama_host})")
        print(f"- 설치된 모델        : {', '.join(models) if models else '없음'}")
        if settings.llm_model not in models:
            print(f"  ! 설정된 모델 '{settings.llm_model}' 이 없습니다. "
                  f"'ollama pull {settings.llm_model}' 을 실행하세요.")
    else:
        print(f"- Ollama             : 연결 실패 ({settings.ollama_host}) → 'ollama serve' 확인")

    index = DocumentIndex(settings)
    try:
        embedder = index.embedder
        print(f"- 임베딩 모델        : {embedder.name} (dim={embedder.dimension})")
    except Exception as exc:
        print(f"- 임베딩 모델        : 사용 불가\n  {exc}")

    try:
        info = index.stats()
        print(f"- 등록 문서          : {info['documents']}건 (활성 {info['active_documents']}건)")
        print(f"- Chunk / Vector     : {info['chunks']} / {info['vectors']} ({info['backend']})")
    except Exception as exc:
        print(f"- 인덱스             : 확인 실패 ({type(exc).__name__}: {exc})")
    return 0


def cmd_add(args) -> int:
    index = DocumentIndex(load_settings())
    results = index.ingest_paths(args.paths, force=args.force)
    for result in results:
        print(f"[{result.status}] {result.filename} - {result.message} (chunks={result.chunk_count})")
    return 0 if all(result.ok for result in results) else 1


def cmd_addfolder(args) -> int:
    index = DocumentIndex(load_settings())
    results = index.ingest_folder(args.folder, recursive=not args.no_recursive, force=args.force)
    for result in results:
        print(f"[{result.status}] {result.filename} - {result.message} (chunks={result.chunk_count})")
    print(f"총 {len(results)}건 처리")
    return 0


def cmd_list(args) -> int:
    index = DocumentIndex(load_settings())
    rows = index.documents()
    if not rows:
        print("등록된 문서가 없습니다.")
        return 0
    print(f"{'ID':>4} {'상태':<8} {'버전':<8} {'Chunk':>6}  문서명")
    print("-" * 78)
    for row in rows:
        print(
            f"{row['id']:>4} {row['status']:<8} {row['version'] or '-':<8} "
            f"{row['chunk_count']:>6}  {row['title']} ({row['filename']})"
        )
    return 0


def cmd_delete(args) -> int:
    index = DocumentIndex(load_settings())
    ok = index.delete_document(args.document_id)
    print("삭제 완료" if ok else "해당 문서를 찾을 수 없습니다.")
    return 0 if ok else 1


def cmd_reindex(args) -> int:
    index = DocumentIndex(load_settings())
    result = index.reindex_document(args.document_id)
    print(f"[{result.status}] {result.message} (chunks={result.chunk_count})")
    return 0 if result.ok else 1


def cmd_status(args) -> int:
    index = DocumentIndex(load_settings())
    index.set_status(args.document_id, active=args.active == "on")
    print(f"문서 {args.document_id} 상태를 {'활성' if args.active == 'on' else '비활성'}으로 변경했습니다.")
    return 0


def cmd_search(args) -> int:
    settings = load_settings()
    index = DocumentIndex(settings)
    result = search(index, args.query, settings)
    if not result.hits and not result.weak_hits:
        print("검색 결과가 없습니다.")
        return 0
    for number, hit in enumerate(result.hits or result.weak_hits, start=1):
        label = "" if result.hits else "(관련도 낮음) "
        print(f"\n{label}[{number}] {hit.citation}")
        print(f"    score={hit.score:.3f} (vector={hit.vector_score:.3f}, keyword={hit.keyword_score:.3f})")
        snippet = hit.body.replace("\n", " ")[:200]
        print(f"    {snippet}...")
    return 0


def cmd_ask(args) -> int:
    settings = load_settings()
    engine = RagEngine(settings)
    answer = engine.ask(args.query)
    print(answer.text)
    if answer.hits:
        print("\n[참고한 문서]")
        for number, hit in enumerate(answer.hits, start=1):
            print(f"  {number}. {hit.citation}  (Similarity {hit.vector_score:.2f} / Score {hit.score:.2f})")
    return 0


def cmd_backup(args) -> int:
    path = create_backup()
    print(f"백업 생성: {path}")
    existing = list_backups()
    if len(existing) > 1:
        print(f"보관 중인 백업: {len(existing)}개")
    return 0


def cmd_config(args) -> int:
    settings = load_settings()
    if args.set:
        for item in args.set:
            if "=" not in item:
                print(f"형식 오류: {item} (key=value)")
                return 1
            key, value = item.split("=", 1)
            if not hasattr(settings, key):
                print(f"알 수 없는 설정: {key}")
                return 1
            current = getattr(settings, key)
            caster = type(current)
            try:
                setattr(settings, key, caster(value) if caster is not bool else value.lower() in ("1", "true", "on", "yes"))
            except ValueError:
                print(f"값 형식 오류: {key}={value}")
                return 1
        save_settings(settings)
        print("설정을 저장했습니다.")
    for key, value in settings.to_dict().items():
        print(f"  {key} = {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="사내 지침 챗봇 - 로컬 관리 도구"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="로컬 환경 점검").set_defaults(func=cmd_doctor)

    add_parser = subparsers.add_parser("add", help="문서 등록")
    add_parser.add_argument("paths", nargs="+")
    add_parser.add_argument("--force", action="store_true", help="이미 등록된 문서도 다시 색인")
    add_parser.set_defaults(func=cmd_add)

    folder_parser = subparsers.add_parser("addfolder", help="폴더 단위 등록")
    folder_parser.add_argument("folder")
    folder_parser.add_argument("--no-recursive", action="store_true")
    folder_parser.add_argument("--force", action="store_true")
    folder_parser.set_defaults(func=cmd_addfolder)

    subparsers.add_parser("list", help="등록 문서 목록").set_defaults(func=cmd_list)

    delete_parser = subparsers.add_parser("delete", help="문서 삭제(원본/인덱스 포함)")
    delete_parser.add_argument("document_id", type=int)
    delete_parser.set_defaults(func=cmd_delete)

    reindex_parser = subparsers.add_parser("reindex", help="문서 재색인")
    reindex_parser.add_argument("document_id", type=int)
    reindex_parser.set_defaults(func=cmd_reindex)

    status_parser = subparsers.add_parser("status", help="문서 활성/비활성 변경")
    status_parser.add_argument("document_id", type=int)
    status_parser.add_argument("active", choices=["on", "off"])
    status_parser.set_defaults(func=cmd_status)

    search_parser = subparsers.add_parser("search", help="검색만 수행(LLM 미사용)")
    search_parser.add_argument("query")
    search_parser.set_defaults(func=cmd_search)

    ask_parser = subparsers.add_parser("ask", help="질문 후 근거 기반 답변")
    ask_parser.add_argument("query")
    ask_parser.set_defaults(func=cmd_ask)

    subparsers.add_parser("backup", help="로컬 백업 생성").set_defaults(func=cmd_backup)

    config_parser = subparsers.add_parser("config", help="설정 확인/변경")
    config_parser.add_argument("--set", nargs="*", metavar="KEY=VALUE")
    config_parser.set_defaults(func=cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LocalLLMError as exc:
        print(f"[LLM 오류] {exc}")
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())

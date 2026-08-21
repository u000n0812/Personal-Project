"""오프라인/보안 검증 스크립트 (요구사항 1.3, 22 / Phase 9).

두 가지를 확인한다.

1. 코드 검사 : 외부 통신을 유발할 수 있는 코드가 있는지 정적 검사
2. 동작 검사 : 네트워크 차단 가드를 켠 상태에서 등록→검색이 정상 동작하는지 확인

    python scripts/check_offline.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCAN_DIRS = ("app", "ui", "scripts")
SCAN_SKIP = {"check_offline.py", "prepare_models.py"}  # 다운로드 안내/검사 스크립트 자체

# 외부 서비스 호출 흔적으로 간주하는 패턴
FORBIDDEN_PATTERNS = [
    (r"\bimport\s+requests\b", "requests 라이브러리 사용"),
    (r"\bimport\s+httpx\b", "httpx 라이브러리 사용"),
    (r"\bopenai\b", "OpenAI API"),
    (r"\banthropic\b", "Anthropic API"),
    (r"\bgenerativelanguage\b|\bgemini\b", "Gemini API"),
    (r"\bbedrock\b", "AWS Bedrock"),
    (r"\bcohere\b", "Cohere API"),
    (r"\bazure\b.*\bopenai\b", "Azure OpenAI"),
    (r"https?://(?!127\.0\.0\.1|localhost)[a-z0-9.-]+\.[a-z]{2,}", "외부 URL"),
    (r"\bsentry_sdk\b|\bposthog\b|\bmixpanel\b|segment\.com", "telemetry/analytics"),
]

# 문서/주석에 등장하는 안내용 URL 은 허용한다.
ALLOWED_URL_CONTEXTS = ("ollama.com", "huggingface.co", "code.claude.com")


def scan_sources() -> list[str]:
    problems: list[str] = []
    for directory in SCAN_DIRS:
        for path in (ROOT / directory).rglob("*.py"):
            if path.name in SCAN_SKIP:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                for pattern, label in FORBIDDEN_PATTERNS:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        if any(allowed in stripped for allowed in ALLOWED_URL_CONTEXTS):
                            continue
                        # 차단 목록 자체를 정의하는 코드(netguard 등)는 제외
                        if "netguard" in path.name or "check_offline" in path.name:
                            continue
                        problems.append(
                            f"{path.relative_to(ROOT)}:{number} [{label}] {stripped[:80]}"
                        )
    return problems


def run_functional_check() -> list[str]:
    """네트워크 차단 상태에서 등록→검색이 되는지 확인한다."""
    import os

    problems: list[str] = []
    workspace = Path(tempfile.mkdtemp(prefix="offline-check-"))
    os.environ["CHATBOT_DATA_DIR"] = str(workspace)
    os.environ.setdefault("CHATBOT_EMBEDDER", "hash")  # 모델 없이도 검사 가능

    from app import netguard

    netguard.install()

    from app.config import load_settings
    from app.pipeline import DocumentIndex
    from app.search import search

    sample = workspace / "Offline_Test_Guideline_v1.0.txt"
    sample.write_text(
        "1. 목적\n오프라인 검증용 문서이다.\n\n"
        "2. 절차\nExternal Data 전달 시 파일을 암호화하고 Password 는 별도 Email 로 전달한다.\n",
        encoding="utf-8",
    )

    settings = load_settings()
    index = DocumentIndex(settings)
    result = index.ingest_file(sample)
    if not result.ok:
        problems.append(f"문서 등록 실패: {result.message}")

    hits = search(index, "Password 전달 방법", settings)
    if not hits.has_results:
        problems.append("검색 결과 없음 (오프라인 검색 실패)")

    if not index.delete_document(int(index.documents()[0]["id"])):
        problems.append("문서 삭제 실패")

    # 외부 연결이 실제로 차단되는지 확인
    import socket

    try:
        socket.create_connection(("example.com", 80), timeout=2)
        problems.append("외부 연결이 차단되지 않았습니다.")
    except netguard.OutboundNetworkBlocked:
        pass
    except OSError:
        pass  # 이미 네트워크가 끊긴 환경

    return problems


def main() -> int:
    print("=== 1) 코드 정적 검사 ===")
    code_problems = scan_sources()
    if code_problems:
        for problem in code_problems:
            print(f"  [발견] {problem}")
    else:
        print("  외부 API / telemetry 호출 코드 없음")

    print("\n=== 2) 오프라인 동작 검사 ===")
    runtime_problems = run_functional_check()
    if runtime_problems:
        for problem in runtime_problems:
            print(f"  [실패] {problem}")
    else:
        print("  네트워크 차단 상태에서 등록/검색/삭제 정상")

    total = len(code_problems) + len(runtime_problems)
    print("\n=== 결과 ===")
    print("  통과" if total == 0 else f"  확인 필요 {total}건")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

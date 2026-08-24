"""외부 통신 차단 및 오프라인 동작을 보장하기 위한 보안 모듈.

이 패키지의 다른 모듈보다 먼저 import 되어야 한다(`guidebot/__init__.py`에서 처리).
- 서드파티 라이브러리의 telemetry / 자동 다운로드를 환경변수로 끈다.
- 네트워크 접속 대상이 loopback(127.0.0.1)인지 검사하는 헬퍼를 제공한다.
- 소스코드에 외부 API 호출이 없는지 검사하는 self-check 기능을 제공한다.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

# --------------------------------------------------------------------------
# 1) 서드파티 telemetry / 원격 호출 비활성화 (import 시 즉시 적용)
# --------------------------------------------------------------------------
_OFFLINE_ENV = {
    # HuggingFace / sentence-transformers
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
    "TOKENIZERS_PARALLELISM": "false",
    # Streamlit
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    "STREAMLIT_SERVER_ADDRESS": "127.0.0.1",
    "STREAMLIT_SERVER_HEADLESS": "true",
    # 기타 공통 telemetry opt-out
    "DO_NOT_TRACK": "1",
    "SCARF_NO_ANALYTICS": "true",
    "ANONYMIZED_TELEMETRY": "False",
    "POSTHOG_DISABLED": "1",
}

# 모델을 처음 내려받아야 하는 상황(최초 1회 준비 단계)에서만 1로 설정한다.
ALLOW_MODEL_DOWNLOAD_ENV = "GUIDEBOT_ALLOW_MODEL_DOWNLOAD"


def apply_offline_env() -> None:
    """telemetry/자동 다운로드 관련 환경변수를 강제한다."""
    allow_download = os.environ.get(ALLOW_MODEL_DOWNLOAD_ENV, "0") == "1"
    for key, value in _OFFLINE_ENV.items():
        if allow_download and key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
            # 모델 최초 다운로드 단계에서만 예외적으로 해제한다.
            os.environ.pop(key, None)
            continue
        os.environ[key] = value


# --------------------------------------------------------------------------
# 2) loopback 전용 접속 검사
# --------------------------------------------------------------------------
class ExternalConnectionBlocked(RuntimeError):
    """loopback 이외의 주소로 접속을 시도할 때 발생한다."""


def is_loopback_host(host: str) -> bool:
    """host 가 로컬 PC 내부(loopback)를 가리키는지 판단한다."""
    if not host:
        return False
    host = host.strip().strip("[]").lower()
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    # 호스트명이 들어온 경우: DNS 조회 없이 거부한다(외부 조회 자체를 하지 않음).
    return False


def assert_local_url(url: str) -> str:
    """URL이 로컬 주소가 아니면 예외를 발생시킨다."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ExternalConnectionBlocked(f"지원하지 않는 프로토콜입니다: {parsed.scheme}")
    if not is_loopback_host(parsed.hostname or ""):
        raise ExternalConnectionBlocked(
            f"외부 주소 접속이 차단되었습니다: {parsed.hostname}. "
            "이 프로그램은 127.0.0.1(로컬)로만 통신합니다."
        )
    return url


def local_port_open(host: str = "127.0.0.1", port: int = 11434, timeout: float = 0.7) -> bool:
    """로컬 포트가 열려 있는지 확인한다(외부 접속 없음)."""
    if not is_loopback_host(host):
        raise ExternalConnectionBlocked(f"loopback 주소가 아닙니다: {host}")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# 3) 소스코드 self-check (Phase 9 보안 검증용)
# --------------------------------------------------------------------------
FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"api\.openai\.com", "OpenAI API"),
    (r"api\.anthropic\.com", "Anthropic API"),
    (r"generativelanguage\.googleapis\.com", "Gemini API"),
    (r"\.openai\.azure\.com", "Azure OpenAI"),
    (r"bedrock[\w.-]*\.amazonaws\.com", "AWS Bedrock"),
    (r"api\.cohere\.ai", "Cohere API"),
    (r"\bimport\s+openai\b", "openai SDK"),
    (r"\bimport\s+anthropic\b", "anthropic SDK"),
    (r"\bimport\s+cohere\b", "cohere SDK"),
    (r"sentry_sdk", "외부 crash report"),
    (r"posthog", "외부 analytics"),
    (r"segment\.io", "외부 analytics"),
    (r"google-analytics\.com", "외부 analytics"),
)

_URL_RE = re.compile(r"https?://([A-Za-z0-9_.\-\[\]:]+)")


def scan_source_tree(root: Path | str) -> list[str]:
    """소스 트리에서 외부 통신 흔적을 찾아 문제 목록을 돌려준다.

    반환 목록이 비어 있으면 외부 통신 코드가 없다는 뜻이다.
    """
    root = Path(root)
    problems: list[str] = []
    skip_dirs = {".git", "data", "backup", "__pycache__", ".venv", "venv", "node_modules"}

    for path in sorted(root.rglob("*.py")):
        if any(part in skip_dirs for part in path.parts):
            continue
        rel = path.relative_to(root)
        if rel.as_posix() == "guidebot/security.py":
            # 이 파일은 금지 패턴 목록 자체를 담고 있으므로 검사 대상에서 제외한다.
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern, label in FORBIDDEN_PATTERNS:
            if re.search(pattern, text):
                problems.append(f"{rel}: 금지된 외부 서비스 사용 흔적({label})")
        for host in _URL_RE.findall(text):
            hostname = host.split(":")[0]
            if not is_loopback_host(hostname):
                problems.append(f"{rel}: 외부 URL 사용({hostname})")
    return problems

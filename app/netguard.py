"""외부 네트워크 차단 가드 (요구사항 1.1 / 1.3 / Phase 9).

프로그램이 실행되는 동안 loopback(127.0.0.1, ::1) 이외의 주소로는
소켓 연결이 아예 열리지 않도록 표준 라이브러리 socket을 감싼다.

- 로컬 LLM(Ollama)은 127.0.0.1 이므로 정상 동작한다.
- 라이브러리가 몰래 telemetry / 모델 다운로드를 시도하면 즉시 차단되고
  ``OutboundNetworkBlocked`` 예외가 발생한다.

모델을 처음 내려받을 때만 ``scripts/prepare_models.py`` 가 가드를 끈 상태로
실행되며, 그 외 애플리케이션 경로에서는 항상 켜진 상태로 동작한다.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Iterable

# 텔레메트리 계열 라이브러리를 사전에 비활성화한다.
TELEMETRY_ENV = {
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
    "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    "DO_NOT_TRACK": "1",
    "ANONYMIZED_TELEMETRY": "False",
    "SCARF_NO_ANALYTICS": "true",
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    "SENTENCE_TRANSFORMERS_HOME": "",  # apply_offline_env 에서 채운다
}

OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}


class OutboundNetworkBlocked(RuntimeError):
    """loopback 이외 주소로 나가려는 연결이 차단되었을 때 발생."""


_installed = False
_orig_socket_connect = socket.socket.connect
_orig_socket_connect_ex = socket.socket.connect_ex
_orig_create_connection = socket.create_connection


def _is_loopback(host: str) -> bool:
    if host in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # 도메인 이름은 곧 외부 주소이므로 허용하지 않는다.
        return False


def _check_address(address) -> None:
    # AF_UNIX 등 tuple 이 아닌 주소는 로컬 통신이므로 통과시킨다.
    if not isinstance(address, tuple) or not address:
        return
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("utf-8", "ignore")
    if not _is_loopback(str(host)):
        raise OutboundNetworkBlocked(
            f"외부 네트워크 연결이 차단되었습니다: {host}. "
            "이 프로그램은 로컬(127.0.0.1) 통신만 허용합니다."
        )


def install(env_only: bool = False) -> None:
    """네트워크 가드를 설치한다. 이미 설치되어 있으면 아무 것도 하지 않는다."""
    global _installed
    apply_offline_env()
    if env_only or _installed:
        return

    def guarded_connect(self, address):  # noqa: ANN001
        _check_address(address)
        return _orig_socket_connect(self, address)

    def guarded_connect_ex(self, address):  # noqa: ANN001
        _check_address(address)
        return _orig_socket_connect_ex(self, address)

    def guarded_create_connection(address, *args, **kwargs):  # noqa: ANN001
        _check_address(address)
        return _orig_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    _installed = True


def uninstall() -> None:
    """가드를 해제한다(모델 최초 다운로드 시에만 사용)."""
    global _installed
    socket.socket.connect = _orig_socket_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _orig_socket_connect_ex  # type: ignore[method-assign]
    socket.create_connection = _orig_create_connection  # type: ignore[assignment]
    _installed = False


def is_installed() -> bool:
    return _installed


def apply_offline_env(offline: bool = True) -> None:
    """telemetry / 온라인 조회를 끄는 환경변수를 설정한다."""
    from app.config import MODELS_DIR  # 순환 import 방지를 위해 지연 import

    env = dict(TELEMETRY_ENV)
    env["SENTENCE_TRANSFORMERS_HOME"] = str(MODELS_DIR)
    env["HF_HOME"] = str(MODELS_DIR)
    if offline:
        env.update(OFFLINE_ENV)
    else:
        for key in OFFLINE_ENV:
            os.environ.pop(key, None)
    for key, value in env.items():
        os.environ[key] = value


def outbound_hosts_in_use() -> Iterable[str]:
    """현재 설정에서 접속하는 호스트 목록(보안 점검 화면 표시용)."""
    from app.config import load_settings

    settings = load_settings()
    host = settings.ollama_host.split("//")[-1].split("/")[0]
    return [host]

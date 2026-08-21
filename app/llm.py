"""로컬 LLM 연결 (요구사항 4 - Local LLM / Phase 1).

Ollama 를 127.0.0.1 로만 호출한다. 외부 AI API 는 사용하지 않는다.
프록시 환경변수(HTTP_PROXY 등)를 무시하도록 opener 를 직접 구성해
로컬 요청이 외부로 새어 나가지 않게 한다.
"""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator, Sequence
from urllib.parse import urlparse

from app.logging_setup import get_logger

logger = get_logger("llm")

DEFAULT_TIMEOUT = 600


class LocalLLMError(RuntimeError):
    """로컬 LLM 호출 실패."""


class NonLocalHostError(LocalLLMError):
    """127.0.0.1 이외의 호스트를 설정한 경우."""


def _assert_loopback(host_url: str) -> None:
    parsed = urlparse(host_url)
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "::1"):
        return
    try:
        if ipaddress.ip_address(hostname).is_loopback:
            return
    except ValueError:
        pass
    raise NonLocalHostError(
        f"로컬(127.0.0.1) 주소만 허용됩니다. 설정된 주소: {host_url}"
    )


@dataclass
class OllamaClient:
    host: str = "http://127.0.0.1:11434"
    timeout: int = DEFAULT_TIMEOUT

    def __post_init__(self) -> None:
        _assert_loopback(self.host)
        # 프록시를 타지 않는 전용 opener
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ------------------------------------------------------------------
    def _request(self, path: str, payload: dict | None = None, timeout: int | None = None):
        url = f"{self.host.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data else "GET",
        )
        try:
            return self._opener.open(request, timeout=timeout or self.timeout)
        except urllib.error.URLError as exc:
            raise LocalLLMError(
                "로컬 LLM(Ollama)에 연결할 수 없습니다. "
                "Ollama 가 실행 중인지 확인하세요. (명령: ollama serve)"
            ) from exc

    # ------------------------------------------------------------------
    def health(self) -> bool:
        try:
            with self._request("/api/tags", timeout=5) as response:
                return response.status == 200
        except LocalLLMError:
            return False

    def list_models(self) -> list[str]:
        try:
            with self._request("/api/tags", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (LocalLLMError, json.JSONDecodeError):
            return []
        return [model.get("name", "") for model in payload.get("models", []) if model.get("name")]

    def chat(
        self,
        messages: Sequence[dict],
        *,
        model: str,
        temperature: float = 0.1,
        num_predict: int = 1024,
    ) -> str:
        payload = {
            "model": model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        with self._request("/api/chat", payload) as response:
            body = json.loads(response.read().decode("utf-8"))
        if "error" in body:
            raise LocalLLMError(str(body["error"]))
        return str(body.get("message", {}).get("content", "")).strip()

    def chat_stream(
        self,
        messages: Sequence[dict],
        *,
        model: str,
        temperature: float = 0.1,
        num_predict: int = 1024,
    ) -> Iterator[str]:
        payload = {
            "model": model,
            "messages": list(messages),
            "stream": True,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        with self._request("/api/chat", payload) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise LocalLLMError(str(chunk["error"]))
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if chunk.get("done"):
                    break

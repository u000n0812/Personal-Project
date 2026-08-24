"""로컬 LLM(Ollama) 호출 클라이언트.

- 127.0.0.1(로컬)로만 통신한다. 외부 주소는 security 모듈이 차단한다.
- 표준 라이브러리(urllib)만 사용하며, 프록시를 우회해 로컬로 직접 연결한다.
- 외부 AI API(OpenAI/Anthropic/Gemini 등)는 사용하지 않는다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator, Sequence
from urllib.parse import urlparse

from .logging_setup import get_logger
from .security import assert_local_url, local_port_open

logger = get_logger("llm")


class LLMError(RuntimeError):
    """로컬 LLM 호출 실패."""


# Ollama에서 흔히 쓰이는 임베딩 전용 모델의 이름 패턴.
# 이런 모델은 문장을 벡터로 바꾸는 것만 지원하며 /api/chat으로 대화 답변을
# 생성할 수 없다(모델 자체에 대화 템플릿이 없다). 이름만으로 판단하는
# 휴리스틱이라 완벽하지 않지만, Ollama 레지스트리의 주요 임베딩 모델
# (bge-*, e5-*, gte-*, nomic-embed-*, mxbai-embed-*, all-minilm 등)은
# 모두 이 패턴에 걸린다.
_EMBEDDING_MODEL_HINTS = ("embed", "bge", "e5", "gte", "minilm")


def looks_like_embedding_model(model_name: str) -> bool:
    """모델 이름이 임베딩 전용 모델처럼 보이는지 이름으로 추정한다.

    답변 생성(Chat)용으로 임베딩 전용 모델을 선택하면 항상 실패하는데,
    Ollama가 돌려주는 오류 메시지만으로는 사용자가 원인(모델 종류 착각)을
    알아채기 어렵다. 이 휴리스틱으로 그 상황을 미리 감지해 안내한다.
    """
    base_name = model_name.split(":")[0].strip().lower()
    if not base_name:
        return False
    return any(hint in base_name for hint in _EMBEDDING_MODEL_HINTS)


@dataclass
class ChatMessage:
    role: str   # system | user | assistant
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class OllamaClient:
    """Ollama REST API(로컬)를 감싼 최소 클라이언트."""

    def __init__(self, host: str = "http://127.0.0.1:11434", timeout: int = 180) -> None:
        self.host = host.rstrip("/")
        assert_local_url(self.host)
        self.timeout = timeout
        # 로컬 호출에는 시스템 프록시를 사용하지 않는다(외부 경유 방지).
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ------------------------------------------------------------------
    def _request(self, path: str, payload: dict | None = None, method: str = "POST"):
        url = assert_local_url(f"{self.host}{path}")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        try:
            return self._opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
                detail = json.loads(body).get("error", "")[:200]
            except Exception:
                detail = ""
            model = (payload or {}).get("model", "")
            if exc.code == 404 and model:
                raise LLMError(
                    f"모델 '{model}' 을(를) 찾을 수 없습니다. "
                    f"터미널에서 설치하세요:  ollama pull {model}"
                ) from exc
            raise LLMError(f"로컬 LLM 오류 (HTTP {exc.code}){': ' + detail if detail else ''}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise LLMError(
                "로컬 LLM에 연결하지 못했습니다. Ollama가 실행 중인지 확인하세요 "
                "(터미널에서 `ollama serve`)."
            ) from exc

    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        parsed = urlparse(self.host)
        return local_port_open(parsed.hostname or "127.0.0.1", parsed.port or 11434)

    def list_models(self) -> list[str]:
        try:
            with self._request("/api/tags", method="GET") as response:
                data = json.loads(response.read().decode("utf-8"))
        except LLMError:
            return []
        return [str(m.get("name", "")) for m in data.get("models", []) if m.get("name")]

    def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float = 0.1,
        num_predict: int | None = None,
    ) -> str:
        """대화형 호출. 전체 답변 문자열을 반환한다."""
        payload = {
            "model": model,
            "messages": [m.as_dict() for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if num_predict:
            payload["options"]["num_predict"] = num_predict
        with self._request("/api/chat", payload) as response:
            body = json.loads(response.read().decode("utf-8"))
        if "error" in body:
            raise LLMError(f"로컬 LLM 오류: {body['error']}")
        content = (body.get("message") or {}).get("content", "")
        if not content:
            raise LLMError("로컬 LLM이 빈 응답을 반환했습니다.")
        return content.strip()

    def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float = 0.1,
        num_predict: int | None = None,
    ) -> Iterator[str]:
        """토큰 단위로 답변을 흘려보낸다(UI 응답성 향상)."""
        payload = {
            "model": model,
            "messages": [m.as_dict() for m in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        if num_predict:
            payload["options"]["num_predict"] = num_predict
        with self._request("/api/chat", payload) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    body = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if body.get("error"):
                    raise LLMError(f"로컬 LLM 오류: {body['error']}")
                piece = (body.get("message") or {}).get("content", "")
                if piece:
                    yield piece
                if body.get("done"):
                    break

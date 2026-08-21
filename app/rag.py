"""RAG 답변 생성 (요구사항 10, 11, 12, 16 / Phase 5, 6).

- 검색된 지침문서 내용만 근거로 답변한다.
- 근거가 없으면 답변을 만들지 않고 고정 문구로 응답한다.
- 답변 끝에는 항상 출처를 표시한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Sequence

from app.config import (
    NO_ANSWER_MESSAGE,
    WEAK_ANSWER_MESSAGE,
    Settings,
)
from app.llm import LocalLLMError, OllamaClient
from app.logging_setup import get_logger
from app.pipeline import DocumentIndex
from app.search import SearchHit, SearchResult, search

logger = get_logger("rag")

SYSTEM_PROMPT = f"""너는 회사 내부 지침문서를 검색하여 답변하는 Assistant이다.

반드시 아래 규칙을 지킨다.

1. 제공된 [참고 문서] 내용만 근거로 답변한다.
2. 문서에서 확인되지 않는 내용을 추측하거나 일반 지식으로 만들어내지 않는다.
3. 근거를 찾을 수 없으면 정확히 다음 문장만 출력한다:
   "{NO_ANSWER_MESSAGE}"
4. 여러 문서에서 관련 내용이 발견되면 문서별로 구분하여 설명한다.
5. 문장 중간이나 끝에 근거 번호를 [1], [2] 형태로 표시한다.
6. 한국어로, 업무 절차를 실제로 수행할 수 있도록 단계/조건 중심으로 간결하게 설명한다.
7. 문서에 없는 담당자, 기한, 시스템 이름을 지어내지 않는다."""

# 후속 질문에서 이전 맥락이 필요한지 판단하는 단서 (요구사항 16)
ANAPHORA_PATTERN = re.compile(
    r"(그럼|그러면|그거|그건|이건|이거|해당|위에|앞에|방금|다시|그 다음|then|it|that)",
    re.I,
)


@dataclass
class Answer:
    text: str
    hits: list[SearchHit] = field(default_factory=list)
    status: str = "answered"  # answered | no_result | weak | llm_error
    search_query: str = ""

    @property
    def grounded(self) -> bool:
        return self.status == "answered"


def contextualize_query(question: str, history: Sequence[dict]) -> str:
    """후속 질문에 직전 질문의 맥락을 붙여 검색 정확도를 높인다."""
    question = question.strip()
    previous_questions = [
        message["content"] for message in history if message.get("role") == "user"
    ]
    if not previous_questions:
        return question
    if len(question) <= 20 or ANAPHORA_PATTERN.search(question):
        return f"{previous_questions[-1]} {question}"
    return question


def build_context(hits: Sequence[SearchHit], max_chars: int = 6000) -> str:
    """검색 결과를 번호가 붙은 참고 문서 블록으로 만든다."""
    blocks: list[str] = []
    total = 0
    for number, hit in enumerate(hits, start=1):
        header_parts = [f"[{number}] {hit.title}"]
        if hit.version:
            header_parts.append(f"v{hit.version}")
        if hit.heading_path:
            header_parts.append(f"| {hit.heading_path}")
        if hit.page:
            header_parts.append(f"| Page {hit.page}")
        block = f"{' '.join(header_parts)}\n{hit.body}"
        if total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n---\n\n".join(blocks)


def build_messages(
    question: str,
    hits: Sequence[SearchHit],
    history: Sequence[dict],
    settings: Settings,
) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 최근 대화만 Context 로 전달한다(요구사항 16).
    recent = list(history)[-settings.history_turns * 2 :]
    for message in recent:
        role = message.get("role")
        content = str(message.get("content", ""))
        if role not in ("user", "assistant") or not content.strip():
            continue
        if role == "assistant":
            content = content.split("\n\n출처:")[0][:600]
        messages.append({"role": role, "content": content})

    user_prompt = (
        f"[참고 문서]\n{build_context(hits)}\n\n"
        f"[질문]\n{question}\n\n"
        f"위 [참고 문서]에 근거해서만 답변하세요. "
        f"{settings.answer_max_sentences}문장 이내로 정리하고, "
        f"근거가 부족하면 \"{NO_ANSWER_MESSAGE}\" 라고만 답하세요."
    )
    messages.append({"role": "user", "content": user_prompt})
    return messages


def format_sources(hits: Sequence[SearchHit]) -> str:
    """답변 하단에 붙일 출처 목록 (요구사항 11)."""
    if not hits:
        return ""
    lines = ["출처:"]
    for number, hit in enumerate(hits, start=1):
        lines.append(f"  [{number}] {hit.citation}")
    return "\n".join(lines)


def weak_answer_text(hits: Sequence[SearchHit]) -> str:
    lines = [WEAK_ANSWER_MESSAGE, ""]
    for number, hit in enumerate(hits, start=1):
        lines.append(f"  [{number}] {hit.citation}")
    return "\n".join(lines)


class RagEngine:
    """검색 + 답변 생성을 묶은 진입점."""

    def __init__(self, settings: Settings, index: DocumentIndex | None = None) -> None:
        self.settings = settings
        self.index = index or DocumentIndex(settings)
        self.client = OllamaClient(settings.ollama_host)

    # ------------------------------------------------------------------
    def retrieve(self, question: str, history: Sequence[dict] | None = None) -> SearchResult:
        query = contextualize_query(question, history or [])
        return search(self.index, query, self.settings)

    def ask(self, question: str, history: Sequence[dict] | None = None) -> Answer:
        history = list(history or [])
        result = self.retrieve(question, history)

        if not result.has_results:
            if result.weak_hits:
                return Answer(
                    text=weak_answer_text(result.weak_hits),
                    hits=result.weak_hits,
                    status="weak",
                    search_query=result.query,
                )
            return Answer(text=NO_ANSWER_MESSAGE, status="no_result", search_query=result.query)

        messages = build_messages(question, result.hits, history, self.settings)
        try:
            raw = self.client.chat(
                messages,
                model=self.settings.llm_model,
                temperature=self.settings.temperature,
                num_predict=self.settings.answer_max_sentences * 120,
            )
        except LocalLLMError as exc:
            logger.warning("llm call failed | error=%s", type(exc).__name__)
            return Answer(
                text=(
                    f"{exc}\n\n"
                    "지금은 검색 결과만 표시합니다. 아래 [참고한 문서]에서 원문을 확인하세요."
                ),
                hits=result.hits,
                status="llm_error",
                search_query=result.query,
            )

        return Answer(
            text=self._finalize(raw, result.hits),
            hits=result.hits,
            status="answered",
            search_query=result.query,
        )

    def ask_stream(
        self, question: str, history: Sequence[dict] | None = None
    ) -> tuple[Iterator[str], SearchResult]:
        """UI 스트리밍용. (조각 iterator, 검색 결과) 를 돌려준다."""
        history = list(history or [])
        result = self.retrieve(question, history)

        if not result.has_results:
            text = weak_answer_text(result.weak_hits) if result.weak_hits else NO_ANSWER_MESSAGE
            return iter([text]), result

        messages = build_messages(question, result.hits, history, self.settings)

        def generate() -> Iterator[str]:
            try:
                for piece in self.client.chat_stream(
                    messages,
                    model=self.settings.llm_model,
                    temperature=self.settings.temperature,
                    num_predict=self.settings.answer_max_sentences * 120,
                ):
                    yield piece
            except LocalLLMError as exc:
                yield (
                    f"\n\n{exc}\n"
                    "지금은 검색 결과만 표시합니다. 아래 [참고한 문서]에서 원문을 확인하세요."
                )

        return generate(), result

    # ------------------------------------------------------------------
    @staticmethod
    def _finalize(answer: str, hits: Sequence[SearchHit]) -> str:
        answer = (answer or "").strip()
        if not answer:
            return NO_ANSWER_MESSAGE
        # 모델이 근거 없음으로 답한 경우 출처를 붙이지 않는다.
        if NO_ANSWER_MESSAGE in answer:
            return NO_ANSWER_MESSAGE
        sources = format_sources(hits)
        return f"{answer}\n\n{sources}" if sources else answer

"""RAG 답변 / Hallucination 방지 테스트 (요구사항 10~12, 16 / Phase 5, 6)."""

import pytest

from app.config import NO_ANSWER_MESSAGE, WEAK_ANSWER_MESSAGE
from app.llm import LocalLLMError
from app.rag import RagEngine, build_context, contextualize_query, format_sources
from app.search import SearchHit, SearchResult


class StubLLM:
    """LLM 호출을 대신하는 테스트용 스텁."""

    def __init__(self, reply: str = "답변 내용입니다. [1]", error: bool = False) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[list[dict]] = []

    def chat(self, messages, **kwargs):
        self.calls.append(list(messages))
        if self.error:
            raise LocalLLMError("로컬 LLM(Ollama)에 연결할 수 없습니다.")
        return self.reply

    def chat_stream(self, messages, **kwargs):
        self.calls.append(list(messages))
        if self.error:
            raise LocalLLMError("로컬 LLM(Ollama)에 연결할 수 없습니다.")
        yield self.reply


@pytest.fixture
def engine(index, sample_dir, settings):
    index.ingest_folder(sample_dir)
    engine = RagEngine(settings, index=index)
    engine.client = StubLLM()
    return engine


def test_answer_includes_sources(engine):
    answer = engine.ask("External Data 전달 시 Password 는 어떻게 전달해?")
    assert answer.status == "answered"
    assert "출처:" in answer.text
    assert answer.hits
    assert any("External" in hit.title for hit in answer.hits)


def test_context_passed_to_llm_contains_only_retrieved_documents(engine):
    engine.ask("Password 전달 규칙")
    prompt = engine.client.calls[0][-1]["content"]
    assert "[참고 문서]" in prompt
    assert "Password" in prompt
    assert NO_ANSWER_MESSAGE in prompt  # 근거 부족 시 응답 규칙을 함께 전달한다.


def test_no_search_result_does_not_call_llm(engine, settings):
    settings.score_threshold = 0.95
    answer = engine.ask("구내식당 점심 메뉴는 어떻게 신청해?")
    assert answer.status in ("no_result", "weak")
    assert answer.text.startswith(NO_ANSWER_MESSAGE) or answer.text.startswith(WEAK_ANSWER_MESSAGE)
    assert engine.client.calls == []  # 근거가 없으면 LLM 을 호출하지 않는다


def test_llm_no_answer_reply_is_normalized_without_sources(engine):
    engine.client = StubLLM(reply=f"{NO_ANSWER_MESSAGE}")
    answer = engine.ask("Password 전달 규칙")
    assert answer.text == NO_ANSWER_MESSAGE
    assert "출처:" not in answer.text


def test_llm_failure_falls_back_to_search_results(engine):
    engine.client = StubLLM(error=True)
    answer = engine.ask("Password 전달 규칙")
    assert answer.status == "llm_error"
    assert answer.hits  # 검색 결과는 그대로 보여준다


def test_weak_results_use_weak_message(engine, monkeypatch):
    weak_hit = SearchHit(
        chunk_id=1,
        document_id=1,
        title="Data Management Guideline",
        version="1.4",
        filename="dm.txt",
        stored_path="",
        page=28,
        section="4. 승인",
        heading_path="4. 승인",
        text="본문",
        score=0.25,
    )
    monkeypatch.setattr(
        "app.rag.search",
        lambda *args, **kwargs: SearchResult(query="q", hits=[], weak_hits=[weak_hit]),
    )
    answer = engine.ask("문서에 없는 절차")
    assert answer.status == "weak"
    assert WEAK_ANSWER_MESSAGE in answer.text
    assert "Data Management Guideline" in answer.text
    assert engine.client.calls == []


def test_follow_up_question_inherits_previous_context():
    history = [
        {"role": "user", "content": "External Data 전달 절차 알려줘."},
        {"role": "assistant", "content": "절차 설명"},
    ]
    assert contextualize_query("그럼 Password는?", history).startswith("External Data 전달 절차")
    long_question = "DB Lock 전에 확인해야 하는 항목을 전부 알려줘"
    assert contextualize_query(long_question, history) == long_question


def test_history_is_limited_to_recent_turns(engine, settings):
    settings.history_turns = 1
    history = []
    for i in range(5):
        history.append({"role": "user", "content": f"질문{i}"})
        history.append({"role": "assistant", "content": f"답변{i}"})
    engine.ask("Password 전달 규칙", history=history)
    messages = engine.client.calls[0]
    user_contents = [m["content"] for m in messages if m["role"] == "user"]
    assert "질문0" not in " ".join(user_contents)
    assert "질문4" in " ".join(user_contents)


def test_build_context_marks_page_and_section():
    hit = SearchHit(
        chunk_id=1,
        document_id=1,
        title="Data Transfer Specification",
        version="2.1",
        filename="spec.pdf",
        stored_path="",
        page=12,
        section="5.3 Data Transfer",
        heading_path="5. Transfer > 5.3 Data Transfer",
        text="[문서 위치] 5. Transfer > 5.3 Data Transfer\n파일은 암호화한다.",
    )
    context = build_context([hit])
    assert "[1] Data Transfer Specification v2.1" in context
    assert "Page 12" in context
    assert "파일은 암호화한다." in context
    assert "[문서 위치]" not in context  # 머리말은 본문에서 제거된다

    sources = format_sources([hit])
    assert "Data Transfer Specification v2.1" in sources
    assert "Page 12" in sources

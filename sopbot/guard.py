"""지침문서 범위 밖 답변을 막는 안전장치.

System Prompt만으로는 "문서 내용만 답하라"를 강제할 수 없다(모델이 어길 수 있다).
따라서 두 지점에서 코드로 검사한다.

1. 질문 단계 (scope gate)
   - 지침 조회가 아닌 요청(코드 작성, 번역, 창작 등)
   - 규칙을 무시하게 만들려는 시도(prompt injection)
   → LLM을 호출하지 않고 거부한다.

2. 답변 단계 (grounding check)
   - 생성된 답변을 문장 단위로 나눠, 검색된 문서 본문에 근거가 있는지 확인한다.
   - 근거 없는 문장은 제거하고, 남는 문장이 없으면 답변 자체를 거부한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from .keyword import content_tokens, tokenize
from .logging_setup import get_logger

logger = get_logger("guard")

# --------------------------------------------------------------------------
# 1) 질문 범위 검사
# --------------------------------------------------------------------------
OUT_OF_SCOPE_ANSWER = (
    "이 챗봇은 등록된 지침문서 내용만 답변합니다. "
    "지침문서에서 확인할 수 있는 업무 절차를 질문해 주세요."
)

# 규칙/문서를 무시하게 만들려는 시도
_OVERRIDE_PATTERNS = (
    r"문서\s*(에\s*)?(없어도|없더라도|무시)",
    r"(지침|규칙|제한|설정)\s*(을|를)?\s*무시",
    r"무시하고\s*(답|알려|말)",
    r"(아는\s*대로|알고\s*있는\s*대로|네가\s*아는)",
    r"(일반\s*지식|상식)\s*(으로|로)\s*(답|알려)",
    r"(추측|추정|상상)\s*(해서|으로)\s*(답|알려|만들)",
    r"ignore\s+(all\s+)?(previous|above|prior)",
    r"system\s*prompt",
    r"(너의|당신의)\s*(역할|규칙|지침)\s*(을|를)?\s*(바꿔|변경|해제)",
)

# 지침문서 조회가 아닌 일반 작업 요청
_OFF_TOPIC_PATTERNS = (
    r"(코드|프로그램|스크립트|매크로)\s*(를|을)?\s*(짜|작성|만들|구현)",
    r"(파이썬|python|자바|java|c\+\+|sql)\s*(코드|함수|스크립트)",
    r"(영어|영문|중국어|일본어)\s*로\s*번역",
    r"번역\s*(해줘|해주세요|부탁)",
    r"(시|소설|노래|가사|시나리오)\s*(를|을)?\s*(써|작성|지어)",
    r"(농담|유머|재미있는\s*이야기)",
    r"(주식|투자|종목|코인)\s*(추천|전망)",
    r"(점심|저녁|맛집|메뉴)\s*(추천|뭐)",
    r"(날씨|환율|주가)\s*(알려|어때|어떻)",
)

_OVERRIDE_RE = [re.compile(p, re.IGNORECASE) for p in _OVERRIDE_PATTERNS]
_OFF_TOPIC_RE = [re.compile(p, re.IGNORECASE) for p in _OFF_TOPIC_PATTERNS]


def check_scope(question: str) -> tuple[bool, str]:
    """질문이 지침문서 조회 범위인지 확인한다.

    반환: (허용 여부, 거부 사유 코드)
    """
    text = (question or "").strip()
    if not text:
        return False, "empty"
    for pattern in _OVERRIDE_RE:
        if pattern.search(text):
            return False, "override_attempt"
    for pattern in _OFF_TOPIC_RE:
        if pattern.search(text):
            return False, "off_topic"
    return True, ""


# --------------------------------------------------------------------------
# 2) 답변 근거 검증
# --------------------------------------------------------------------------
# 문장 분리: 종결어미/구두점, 줄바꿈, 목록 기호 기준
_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")
_CITATION_ONLY = re.compile(r"^[\s\-*•\d.)\[\]]+$")
_SOURCE_HEADER = re.compile(r"^\s*(출처|참고\s*문서|sources?)\s*[:：]", re.IGNORECASE)
# 줄 앞 목록 기호("1.", "3)", "-", "•")는 문장 구분자로 보지 않는다
_LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
# 답변에 붙는 인용 표시 [1], [2]
_CITATION_MARK = re.compile(r"\[\d+\]")
_NUMBER = re.compile(r"\d+")


@dataclass
class GroundingReport:
    """답변 문장별 근거 확인 결과."""

    supported: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.supported) + len(self.unsupported)

    @property
    def all_unsupported(self) -> bool:
        return self.total > 0 and not self.supported

    @property
    def summary(self) -> str:
        return f"근거 확인 {len(self.supported)}/{self.total} 문장"


def split_sentences(text: str) -> list[str]:
    """답변을 검증 단위(문장/줄)로 나눈다.

    "1. 첫 번째 항목" 처럼 줄 앞에 붙는 번호는 문장 구분으로 취급하지 않는다.
    """
    sentences: list[str] = []
    for line in (text or "").splitlines():
        stripped = _LIST_MARKER.sub("", line.strip())
        if not stripped:
            continue
        for piece in _SENTENCE_END.split(stripped):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


def sentence_support(
    sentence: str,
    context_tokens: set[str],
    context_numbers: set[str] | None = None,
) -> float:
    """문장의 단어가 검색된 문서 본문에서 확인되는 비율(0~1).

    지침문서에서 숫자(기간, 횟수, 금액)는 의미가 크므로,
    문서에 없는 숫자가 등장하면 근거 없음(0.0)으로 처리한다.
    """
    cleaned = _CITATION_MARK.sub(" ", sentence)   # 인용 표시 [1] 은 검증 대상이 아니다
    if context_numbers is not None:
        for number in _NUMBER.findall(cleaned):
            if number not in context_numbers:
                return 0.0
    tokens = content_tokens(cleaned)
    if not tokens:
        return 1.0   # 목록 기호, 인용 번호 등 판단 대상이 아닌 줄
    matched = sum(1 for token in tokens if token in context_tokens)
    return matched / len(tokens)


def verify_answer(
    answer: str,
    context_texts: Sequence[str],
    min_support: float = 0.5,
) -> GroundingReport:
    """답변 문장이 검색된 문서에 실제로 근거가 있는지 확인한다."""
    context_tokens: set[str] = set()
    context_numbers: set[str] = set()
    for text in context_texts:
        context_tokens.update(tokenize(text))
        context_numbers.update(_NUMBER.findall(text))

    report = GroundingReport()
    for sentence in split_sentences(answer):
        if _SOURCE_HEADER.match(sentence):
            break      # 출처 목록부터는 프로그램이 붙인 내용이므로 검증하지 않는다
        if _CITATION_ONLY.match(sentence):
            continue
        score = sentence_support(sentence, context_tokens, context_numbers)
        report.scores.append(round(score, 3))
        if score >= min_support:
            report.supported.append(sentence)
        else:
            report.unsupported.append(sentence)
    return report


def apply_grounding(
    answer: str,
    context_texts: Sequence[str],
    min_support: float = 0.5,
) -> tuple[str, GroundingReport]:
    """근거 없는 문장을 제거한 답변과 검증 결과를 돌려준다."""
    report = verify_answer(answer, context_texts, min_support)
    if not report.unsupported:
        return answer, report

    logger.info(
        "grounding: removed %d of %d sentences", len(report.unsupported), report.total
    )
    kept = "\n".join(report.supported).strip()
    if not kept:
        return "", report
    note = (
        f"\n\n※ 지침문서에서 확인되지 않은 문장 {len(report.unsupported)}개는 "
        "답변에서 제외했습니다."
    )
    return kept + note, report

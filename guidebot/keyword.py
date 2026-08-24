"""BM25 기반 Keyword 검색 (외부 검색엔진 없이 순수 Python 구현).

한국어/영문 혼용 지침문서를 대상으로 하므로
 - 영문/숫자는 단어 단위로,
 - 한글은 단어 + 글자 bi-gram으로 토큰화한다(조사·어미 변화 흡수).
동의어 사전을 사용해 "DBL" / "DB Lock" / "Database Lock" 같은 표기 차이를 흡수한다.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Sequence

_TOKEN_RE = re.compile(r"[a-z0-9]+|[가-힣]+")

K1 = 1.5
B = 0.75

# 커버리지 계산에서 제외할 일반어(질문 형태소 위주)
STOPWORDS = {
    "어떻게", "무엇", "뭐야", "뭐였지", "알려줘", "해야", "하나요", "인가요", "되나요",
    "얼마나", "얼마", "언제", "누가", "누구", "어디", "해줘", "되지", "였지", "하지",
    "그럼", "그러면", "항목", "경우", "관련", "대해", "있나요", "있어", "인지", "니까",
    "합니까", "됩니까", "무엇인가요", "방법", "절차",
}


def tokenize(text: str) -> list[str]:
    """검색용 토큰 목록을 만든다."""
    tokens: list[str] = []
    for match in _TOKEN_RE.findall(text.lower()):
        tokens.append(match)
        if re.fullmatch(r"[가-힣]+", match) and len(match) > 1:
            tokens.extend(match[i : i + 2] for i in range(len(match) - 1))
    return tokens


def expand_query(query: str, synonyms: dict[str, list[str]]) -> str:
    """동의어 사전을 이용해 질문을 확장한다."""
    lowered = query.lower()
    extras: list[str] = []
    for key, values in synonyms.items():
        if key and key in lowered:
            extras.extend(values)
        else:
            for value in values:
                if value.lower() in lowered:
                    extras.append(key)
                    extras.extend(v for v in values if v.lower() != value.lower())
                    break
    if not extras:
        return query
    unique_extras = list(dict.fromkeys(extras))
    return f"{query} {' '.join(unique_extras)}"


class KeywordIndex:
    """메모리 상주 BM25 Index (문서 수백 개 규모에 충분)."""

    def __init__(self) -> None:
        self.doc_ids: list[int] = []
        self.term_freqs: list[Counter] = []
        self.doc_len: list[int] = []
        self.doc_freq: Counter = Counter()
        self.avg_len: float = 0.0

    def build(self, records: Iterable[tuple[int, str]]) -> "KeywordIndex":
        self.doc_ids, self.term_freqs, self.doc_len = [], [], []
        self.doc_freq = Counter()
        for chunk_id, text in records:
            tokens = tokenize(text)
            counts = Counter(tokens)
            self.doc_ids.append(int(chunk_id))
            self.term_freqs.append(counts)
            self.doc_len.append(len(tokens))
            self.doc_freq.update(counts.keys())
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        return self

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """BM25 점수 상위 top_k를 (chunk_id, score)로 반환한다."""
        if not self.doc_ids or top_k <= 0:
            return []
        query_tokens = [t for t in tokenize(query) if t]
        if not query_tokens:
            return []
        total_docs = len(self.doc_ids)
        scores: list[float] = [0.0] * total_docs

        for token in set(query_tokens):
            df = self.doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            for position, counts in enumerate(self.term_freqs):
                tf = counts.get(token, 0)
                if not tf:
                    continue
                length_norm = 1 - B + B * (self.doc_len[position] / (self.avg_len or 1))
                scores[position] += idf * (tf * (K1 + 1)) / (tf + K1 * length_norm)

        ranked = [
            (self.doc_ids[i], score) for i, score in enumerate(scores) if score > 0.0
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[: min(top_k, len(ranked))]

    def __len__(self) -> int:
        return len(self.doc_ids)


def normalize_scores(results: Sequence[tuple[int, float]]) -> dict[int, float]:
    """서로 다른 검색 점수를 0~1 범위로 정규화한다."""
    if not results:
        return {}
    values = [score for _, score in results]
    lowest, highest = min(values), max(values)
    if math.isclose(highest, lowest):
        return {chunk_id: 1.0 for chunk_id, _ in results}
    span = highest - lowest
    return {chunk_id: (score - lowest) / span for chunk_id, score in results}


def content_tokens(query: str) -> list[str]:
    """커버리지 판단에 사용할 질문 토큰(불용어 제외)."""
    return [
        token
        for token in dict.fromkeys(tokenize(query))
        if len(token) > 1 and token not in STOPWORDS
    ]


def coverage(query: str, texts: Iterable[str]) -> float:
    """질문 토큰 중 검색된 본문에 실제로 등장한 비율(0~1).

    Embedding 모델 종류와 무관하게 비교 가능한 '근거 있음' 신호로 사용한다.
    """
    query_tokens = content_tokens(query)
    if not query_tokens:
        return 0.0
    found: set[str] = set()
    for text in texts:
        found.update(tokenize(text))
    matched = sum(1 for token in query_tokens if token in found)
    return matched / len(query_tokens)

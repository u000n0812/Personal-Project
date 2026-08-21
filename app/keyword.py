"""키워드 검색(BM25) - Hybrid Search 의 2차 검색 (요구사항 9).

외부 검색 엔진(Elasticsearch 등)을 추가하지 않고, 순수 Python 으로 구현한
가벼운 BM25 를 사용한다. 문서 수백 개 수준에서는 충분히 빠르다.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, Sequence

from app.text_utils import tokenize

K1 = 1.5
B = 0.75


class BM25Index:
    """메모리 상주 BM25 역색인."""

    def __init__(self) -> None:
        self.doc_ids: list[int] = []
        self.doc_len: list[int] = []
        self.term_freq: list[Counter] = []
        self.postings: dict[str, list[int]] = {}
        self.avg_len: float = 0.0

    @property
    def size(self) -> int:
        return len(self.doc_ids)

    def build(self, documents: Iterable[tuple[int, str]]) -> "BM25Index":
        self.__init__()  # 재구축 시 초기화
        for doc_id, text in documents:
            tokens = tokenize(text)
            counter = Counter(tokens)
            position = len(self.doc_ids)
            self.doc_ids.append(int(doc_id))
            self.doc_len.append(max(1, len(tokens)))
            self.term_freq.append(counter)
            for term in counter:
                self.postings.setdefault(term, []).append(position)
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        return self

    def search(self, query: str, k: int = 30) -> list[tuple[int, float]]:
        if not self.size:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = {}
        total_docs = self.size
        for term, query_count in Counter(query_tokens).items():
            postings = self.postings.get(term)
            if not postings:
                continue
            doc_freq = len(postings)
            idf = math.log(1 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
            # 질문에 여러 번 등장한 토큰은 약간 가중한다.
            query_weight = 1.0 + 0.2 * (query_count - 1)
            for position in postings:
                freq = self.term_freq[position][term]
                length_norm = 1 - B + B * (self.doc_len[position] / (self.avg_len or 1))
                score = idf * (freq * (K1 + 1)) / (freq + K1 * length_norm)
                scores[position] = scores.get(position, 0.0) + score * query_weight

        ranked = sorted(scores.items(), key=lambda item: -item[1])[:k]
        return [(self.doc_ids[position], score) for position, score in ranked]


def build_from_rows(rows: Sequence) -> BM25Index:
    """SQLite Row(iter_active_chunks 결과)로부터 BM25 인덱스를 만든다.

    제목/버전/Section 을 본문과 함께 색인해 "문서명으로 찾기"도 되게 한다.
    """
    documents: list[tuple[int, str]] = []
    for row in rows:
        parts = [
            str(row["title"] or ""),
            str(row["version"] or ""),
            str(row["heading_path"] or ""),
            str(row["text"] or ""),
        ]
        documents.append((int(row["id"]), "\n".join(parts)))
    return BM25Index().build(documents)

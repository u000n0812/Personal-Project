"""Hybrid 검색: Vector Search + Keyword(BM25) Search 결합.

1차로 Vector 검색, 2차로 Keyword 검색을 수행한 뒤 점수를 정규화해 결합한다.
기본 검색 대상은 '최신 활성 버전' 문서이며, 필요 시 과거 버전도 포함할 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, load_synonyms
from .db import STATUS_ACTIVE, STATUS_SUPERSEDED, Chunk, Database, Document
from .embed import BaseEmbedder
from .keyword import KeywordIndex, coverage, expand_query, normalize_scores
from .logging_setup import get_logger
from .vectorstore import VectorStore

logger = get_logger("search")

INDEX_VERSION_KEY = "index_version"


@dataclass
class SearchResult:
    """검색된 chunk 1건과 출처 정보."""

    chunk: Chunk
    document: Document
    score: float           # 결합 점수 (0~1)
    vector_score: float    # cosine 유사도 원점수
    keyword_score: float   # BM25 원점수

    @property
    def page_label(self) -> str:
        if not self.chunk.page_start:
            return ""
        if self.chunk.page_start == self.chunk.page_end:
            return f"Page {self.chunk.page_start}"
        return f"Page {self.chunk.page_start}-{self.chunk.page_end}"

    @property
    def citation(self) -> str:
        parts = [f"{self.document.title} v{self.document.version}"]
        if self.chunk.section:
            parts.append(f"Section {self.chunk.section}")
        if self.page_label:
            parts.append(self.page_label)
        return " / ".join(parts)


class Retriever:
    """Vector Index + Keyword Index를 함께 사용하는 검색기."""

    def __init__(
        self,
        db: Database,
        store: VectorStore,
        embedder: BaseEmbedder,
        settings: Settings,
    ) -> None:
        self.db = db
        self.store = store
        self.embedder = embedder
        self.settings = settings
        self.synonyms = load_synonyms()
        self._keyword_index = KeywordIndex()
        self._keyword_signature: tuple | None = None
        self._records: dict[int, tuple[Chunk, Document]] = {}

    # ------------------------------------------------------------------
    def _statuses(self, include_superseded: bool | None = None) -> tuple[str, ...]:
        include = (
            self.settings.include_superseded
            if include_superseded is None
            else include_superseded
        )
        return (STATUS_ACTIVE, STATUS_SUPERSEDED) if include else (STATUS_ACTIVE,)

    def _ensure_keyword_index(self, statuses: tuple[str, ...]) -> dict[int, tuple[Chunk, Document]]:
        """검색 대상이 바뀐 경우에만 Keyword Index를 다시 만든다."""
        version = self.db.get_meta(INDEX_VERSION_KEY, "0")
        signature = (version, statuses)
        if self._keyword_signature != signature:
            rows = self.db.iter_chunks_for_search(statuses)
            self._records = {chunk.id: (chunk, document) for chunk, document in rows}
            self._keyword_index.build(
                (
                    chunk.id,
                    f"{document.title} {chunk.heading_path} {chunk.text}",
                )
                for chunk, document in rows
            )
            self._keyword_signature = signature
            logger.info("keyword index rebuilt: chunks=%d", len(self._records))
        return self._records

    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int | None = None,
        include_superseded: bool | None = None,
    ) -> list[SearchResult]:
        """질문과 관련된 chunk를 점수 순으로 반환한다."""
        query = (query or "").strip()
        if not query:
            return []

        top_k = top_k or self.settings.top_k
        candidate_k = max(self.settings.candidate_k, top_k * 3)
        statuses = self._statuses(include_superseded)
        records = self._ensure_keyword_index(statuses)
        if not records:
            return []

        allowed = set(records)

        # 1차: Vector Search
        vector_hits: list[tuple[int, float]] = []
        try:
            query_vector = self.embedder.encode_query(query)
            raw_hits = self.store.search(query_vector, candidate_k * 2)
            vector_hits = [(cid, score) for cid, score in raw_hits if cid in allowed][:candidate_k]
        except Exception as exc:  # Index/모델 문제로 검색 전체가 멈추지 않게 한다.
            logger.error("vector search failed: %s", exc.__class__.__name__)

        # 2차: Keyword Search (동의어 확장 포함)
        expanded = expand_query(query, self.synonyms)
        keyword_hits = [
            (cid, score)
            for cid, score in self._keyword_index.search(expanded, candidate_k)
            if cid in allowed
        ]

        vector_raw = dict(vector_hits)
        keyword_raw = dict(keyword_hits)
        vector_norm = normalize_scores(vector_hits)
        keyword_norm = normalize_scores(keyword_hits)

        weight_keyword = min(max(self.settings.keyword_weight, 0.0), 1.0)
        weight_vector = 1.0 - weight_keyword

        combined: dict[int, float] = {}
        for chunk_id in set(vector_norm) | set(keyword_norm):
            combined[chunk_id] = (
                weight_vector * vector_norm.get(chunk_id, 0.0)
                + weight_keyword * keyword_norm.get(chunk_id, 0.0)
            )

        ranked = sorted(combined.items(), key=lambda item: item[1], reverse=True)[:top_k]
        # 1위 대비 점수가 지나치게 낮은 결과는 출처 목록에서 제외한다(근거 정확도 우선).
        if ranked:
            cutoff = ranked[0][1] * max(0.0, min(self.settings.min_score_ratio, 1.0))
            ranked = [item for item in ranked if item[1] >= cutoff] or ranked[:1]

        results: list[SearchResult] = []
        for chunk_id, score in ranked:
            chunk, document = records[chunk_id]
            results.append(
                SearchResult(
                    chunk=chunk,
                    document=document,
                    score=round(float(score), 4),
                    vector_score=round(float(vector_raw.get(chunk_id, 0.0)), 4),
                    keyword_score=round(float(keyword_raw.get(chunk_id, 0.0)), 4),
                )
            )
        logger.info("search done: candidates=%d returned=%d", len(combined), len(results))
        return results

    # ------------------------------------------------------------------
    def evidence_scores(self, query: str, results: list[SearchResult]) -> tuple[float, float]:
        """(최고 vector 유사도, 질문 단어 커버리지)를 계산한다."""
        if not results:
            return 0.0, 0.0
        best_vector = max(r.vector_score for r in results)
        token_coverage = coverage(query, [r.chunk.text for r in results])
        return best_vector, token_coverage

    def has_sufficient_evidence(self, results: list[SearchResult], query: str = "") -> bool:
        """근거로 삼기에 충분한 검색 결과인지 판단한다(Hallucination 방지).

        - Vector 유사도가 threshold 이상이거나,
        - 질문에 사용된 단어가 검색 본문에서 충분히 확인되면 근거가 있다고 본다.
        Embedding 모델마다 유사도 분포가 다르므로 두 신호를 함께 사용한다.
        """
        if not results:
            return False
        best_vector, token_coverage = self.evidence_scores(query, results)
        return (
            best_vector >= self.settings.score_threshold
            or token_coverage >= self.settings.min_keyword_coverage
        )

    def invalidate(self) -> None:
        """문서가 추가/삭제된 뒤 Keyword Index를 다시 만들도록 표시한다."""
        self._keyword_signature = None
        self._records = {}

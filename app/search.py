"""Hybrid 검색 (요구사항 9 / Phase 4).

1차 Vector Search + 2차 Keyword(BM25) Search 결과를 가중 합산한다.
표현이 달라도("DBL" / "DB Lock" / "Database Lock") 검색되도록
키워드 검색 전에 동의어를 확장한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.logging_setup import get_logger
from app.pipeline import DocumentIndex
from app.text_utils import expand_query

logger = get_logger("search")


@dataclass
class SearchHit:
    chunk_id: int
    document_id: int
    title: str
    version: str
    filename: str
    stored_path: str
    page: int | None
    section: str
    heading_path: str
    text: str
    vector_score: float = 0.0
    keyword_score: float = 0.0
    score: float = 0.0

    @property
    def citation(self) -> str:
        """출처 표기 문자열 (요구사항 11)."""
        parts = [self.title]
        if self.version:
            parts.append(f"v{self.version}")
        location = []
        if self.heading_path:
            location.append(self.heading_path)
        if self.page:
            location.append(f"Page {self.page}")
        head = " ".join(parts)
        return f"{head} / {' / '.join(location)}" if location else head

    @property
    def body(self) -> str:
        """[문서 위치] 머리말을 제외한 실제 본문."""
        lines = self.text.splitlines()
        if lines and lines[0].startswith("[문서 위치]"):
            return "\n".join(lines[1:]).strip()
        return self.text.strip()


@dataclass
class SearchResult:
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    weak_hits: list[SearchHit] = field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return bool(self.hits)


def _normalize_scores(pairs: list[tuple[int, float]]) -> dict[int, float]:
    """점수를 0~1 로 정규화한다(BM25 는 상한이 없으므로 최댓값 기준)."""
    if not pairs:
        return {}
    highest = max(score for _, score in pairs)
    if highest <= 0:
        return {chunk_id: 0.0 for chunk_id, _ in pairs}
    return {chunk_id: score / highest for chunk_id, score in pairs}


def search(index: DocumentIndex, query: str, settings: Settings | None = None) -> SearchResult:
    settings = settings or index.settings
    query = (query or "").strip()
    if not query:
        return SearchResult(query=query)

    candidate_k = max(settings.candidate_k, settings.top_k * 3)

    # 1차: Vector Search
    vector_pairs: list[tuple[int, float]] = []
    try:
        query_vector = index.embedder.encode_query(query)
        vector_pairs = index.store.search(query_vector, candidate_k * 2)
    except Exception as exc:  # 임베딩 모델이 없어도 키워드 검색은 동작하게 한다
        logger.warning("vector search unavailable | error=%s", type(exc).__name__)

    # 2차: Keyword Search (동의어 확장 적용)
    keyword_pairs = index.bm25.search(expand_query(query), candidate_k)

    vector_scores = {
        chunk_id: max(0.0, min(1.0, score)) for chunk_id, score in vector_pairs
    }
    keyword_scores = _normalize_scores(keyword_pairs)

    weight = max(0.0, min(1.0, settings.vector_weight))
    if not vector_scores:
        weight = 0.0
    elif not keyword_scores:
        weight = 1.0

    combined: dict[int, float] = {}
    for chunk_id in set(vector_scores) | set(keyword_scores):
        combined[chunk_id] = (
            weight * vector_scores.get(chunk_id, 0.0)
            + (1 - weight) * keyword_scores.get(chunk_id, 0.0)
        )

    ranked = sorted(combined.items(), key=lambda item: -item[1])[: candidate_k * 2]
    rows = index.chunk_rows([chunk_id for chunk_id, _ in ranked])

    hits: list[SearchHit] = []
    for chunk_id, score in ranked:
        row = rows.get(chunk_id)
        if row is None or row["status"] != "active":
            continue  # 비활성(과거 버전) 문서는 기본 검색 대상에서 제외한다
        hits.append(
            SearchHit(
                chunk_id=chunk_id,
                document_id=int(row["doc_id"]),
                title=str(row["title"]),
                version=str(row["version"] or ""),
                filename=str(row["filename"]),
                stored_path=str(row["stored_path"]),
                page=int(row["page"]) if row["page"] is not None else None,
                section=str(row["section"] or ""),
                heading_path=str(row["heading_path"] or ""),
                text=str(row["text"]),
                vector_score=vector_scores.get(chunk_id, 0.0),
                keyword_score=keyword_scores.get(chunk_id, 0.0),
                score=score,
            )
        )

    threshold = settings.score_threshold
    strong = [hit for hit in hits if hit.score >= threshold][: settings.top_k]
    weak = [
        hit for hit in hits if threshold > hit.score >= threshold * 0.6
    ][: settings.top_k]

    logger.info(
        "search done | candidates=%s strong=%s weak=%s",
        len(hits),
        len(strong),
        len(weak),
    )
    return SearchResult(query=query, hits=strong, weak_hits=weak)


def open_source_file(stored_path: str) -> bool:
    """출처 문서를 OS 기본 프로그램으로 연다 (요구사항 11).

    로컬 파일만 열며, 외부 URL 은 열지 않는다.
    """
    import os
    import subprocess
    import sys

    path = Path(stored_path)
    if not path.exists():
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("open file failed | error=%s", type(exc).__name__)
        return False

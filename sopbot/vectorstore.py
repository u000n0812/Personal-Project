"""로컬 Vector Index.

별도의 Vector DB 서버를 두지 않는다. data/index 폴더에 파일로 저장하며,
프로그램을 껐다 켜도 Index가 유지된다(재Embedding 불필요).

- numpy가 있으면 numpy 행렬 연산으로 검색한다(기본).
- faiss가 설치돼 있으면 faiss IndexFlatIP로 가속한다(선택).
- 둘 다 없으면 순수 Python으로 계산한다(문서 수가 적을 때 충분).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .config import INDEX_DIR
from .logging_setup import get_logger

logger = get_logger("vectorstore")

Vector = list[float]

try:  # 선택적 의존성
    import numpy as _np
except ImportError:  # pragma: no cover - 환경 의존
    _np = None

try:  # 선택적 의존성(있으면 검색 가속)
    import faiss as _faiss
except ImportError:  # pragma: no cover - 환경 의존
    _faiss = None


class VectorStore:
    """chunk_id 와 vector 를 함께 보관하는 단순 Flat Index."""

    META_FILE = "index_meta.json"
    IDS_FILE = "chunk_ids.json"
    VECTORS_NPY = "vectors.npy"
    VECTORS_JSON = "vectors.jsonl"

    def __init__(self, directory: Path | str | None = None) -> None:
        self.dir = Path(directory) if directory else INDEX_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ids: list[int] = []
        self.vectors: list[Vector] = []
        self.embedder_name: str = ""
        self.dimension: int = 0
        self._faiss_index = None
        self._matrix = None
        self.load()

    # ------------------------------------------------------------------
    # 저장 / 불러오기
    # ------------------------------------------------------------------
    def load(self) -> None:
        meta_path = self.dir / self.META_FILE
        if not meta_path.exists():
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.embedder_name = meta.get("embedder", "")
            self.dimension = int(meta.get("dimension", 0))
            self.ids = [int(i) for i in json.loads(
                (self.dir / self.IDS_FILE).read_text(encoding="utf-8")
            )]
            npy_path = self.dir / self.VECTORS_NPY
            json_path = self.dir / self.VECTORS_JSON
            if _np is not None and npy_path.exists():
                self.vectors = _np.load(npy_path).astype("float32").tolist()
            elif json_path.exists():
                self.vectors = [
                    json.loads(line) for line in json_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            else:
                self.vectors = []
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error("index load failed: %s", exc.__class__.__name__)
            self.ids, self.vectors = [], []
        if len(self.ids) != len(self.vectors):
            logger.error("index inconsistent (ids=%d vectors=%d) -> reset", len(self.ids), len(self.vectors))
            self.ids, self.vectors = [], []
        self._invalidate()

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / self.IDS_FILE).write_text(json.dumps(self.ids), encoding="utf-8")
        npy_path = self.dir / self.VECTORS_NPY
        json_path = self.dir / self.VECTORS_JSON
        if _np is not None:
            array = _np.asarray(self.vectors, dtype="float32") if self.vectors else _np.zeros(
                (0, self.dimension or 1), dtype="float32"
            )
            _np.save(npy_path, array)
            json_path.unlink(missing_ok=True)
        else:
            json_path.write_text(
                "\n".join(json.dumps(v) for v in self.vectors), encoding="utf-8"
            )
            npy_path.unlink(missing_ok=True)
        (self.dir / self.META_FILE).write_text(
            json.dumps(
                {
                    "embedder": self.embedder_name,
                    "dimension": self.dimension,
                    "count": len(self.ids),
                    "backend": "faiss" if _faiss is not None else ("numpy" if _np is not None else "python"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 변경
    # ------------------------------------------------------------------
    def add(self, chunk_ids: Sequence[int], vectors: Sequence[Vector]) -> None:
        if len(chunk_ids) != len(vectors):
            raise ValueError("chunk_ids와 vectors 개수가 다릅니다.")
        if not chunk_ids:
            return
        if not self.dimension:
            self.dimension = len(vectors[0])
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"vector 차원이 다릅니다(index={self.dimension}, input={len(vector)}). "
                    "Embedding 모델을 바꾼 경우 전체 재색인이 필요합니다."
                )
        self.ids.extend(int(i) for i in chunk_ids)
        self.vectors.extend([float(v) for v in vector] for vector in vectors)
        self._invalidate()

    def remove(self, chunk_ids: Sequence[int]) -> int:
        """지정한 chunk를 Index에서 완전히 제거한다."""
        if not chunk_ids:
            return 0
        target = {int(i) for i in chunk_ids}
        kept_ids: list[int] = []
        kept_vectors: list[Vector] = []
        removed = 0
        for chunk_id, vector in zip(self.ids, self.vectors):
            if chunk_id in target:
                removed += 1
                continue
            kept_ids.append(chunk_id)
            kept_vectors.append(vector)
        self.ids, self.vectors = kept_ids, kept_vectors
        self._invalidate()
        return removed

    def reset(self, embedder_name: str = "", dimension: int = 0) -> None:
        self.ids, self.vectors = [], []
        self.embedder_name = embedder_name or self.embedder_name
        self.dimension = dimension or self.dimension
        self._invalidate()

    def _invalidate(self) -> None:
        self._faiss_index = None
        self._matrix = None

    # ------------------------------------------------------------------
    # 검색
    # ------------------------------------------------------------------
    def search(self, query_vector: Sequence[float], top_k: int = 20) -> list[tuple[int, float]]:
        """cosine 유사도 상위 top_k를 (chunk_id, score)로 반환한다."""
        if not self.ids or top_k <= 0:
            return []
        if len(query_vector) != self.dimension:
            raise ValueError(
                f"질문 vector 차원이 Index와 다릅니다(index={self.dimension}, "
                f"query={len(query_vector)}). 전체 재색인이 필요합니다."
            )
        top_k = min(top_k, len(self.ids))

        if _faiss is not None and _np is not None:
            return self._search_faiss(query_vector, top_k)
        if _np is not None:
            return self._search_numpy(query_vector, top_k)
        return self._search_python(query_vector, top_k)

    def _search_faiss(self, query_vector: Sequence[float], top_k: int) -> list[tuple[int, float]]:
        if self._faiss_index is None:
            index = _faiss.IndexFlatIP(self.dimension)
            index.add(_np.asarray(self.vectors, dtype="float32"))
            self._faiss_index = index
        query = _np.asarray([query_vector], dtype="float32")
        scores, positions = self._faiss_index.search(query, top_k)
        return [
            (self.ids[int(pos)], float(score))
            for pos, score in zip(positions[0], scores[0])
            if 0 <= int(pos) < len(self.ids)
        ]

    def _search_numpy(self, query_vector: Sequence[float], top_k: int) -> list[tuple[int, float]]:
        if self._matrix is None:
            self._matrix = _np.asarray(self.vectors, dtype="float32")
        scores = self._matrix @ _np.asarray(query_vector, dtype="float32")
        order = _np.argsort(-scores)[:top_k]
        return [(self.ids[int(i)], float(scores[int(i)])) for i in order]

    def _search_python(self, query_vector: Sequence[float], top_k: int) -> list[tuple[int, float]]:
        scored = [
            (chunk_id, sum(a * b for a, b in zip(vector, query_vector)))
            for chunk_id, vector in zip(self.ids, self.vectors)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def __len__(self) -> int:
        return len(self.ids)

    @property
    def backend(self) -> str:
        if _faiss is not None and _np is not None:
            return "faiss"
        return "numpy" if _np is not None else "python"

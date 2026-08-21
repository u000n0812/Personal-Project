"""로컬 Vector Index (요구사항 4 - Vector Search / Phase 3).

별도 Vector DB 서버를 두지 않고 파일로만 저장한다.

- FAISS 가 설치되어 있으면 ``IndexIDMap2(IndexFlatIP)`` 를 사용한다.
- 없으면 numpy 브루트포스 검색으로 자동 대체한다.
  (문서 100~500개 / 청크 수만 개 수준에서는 성능 차이가 크지 않다.)

두 방식 모두 정규화된 벡터의 내적 = 코사인 유사도를 사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np

from app.config import INDEX_DIR
from app.logging_setup import get_logger

logger = get_logger("vector")

META_FILE = "index_meta.json"
NUMPY_VECTORS = "vectors.npy"
NUMPY_IDS = "ids.npy"
FAISS_FILE = "faiss.index"

try:  # pragma: no cover - 환경에 따라 달라짐
    import faiss  # type: ignore

    FAISS_AVAILABLE = True
except Exception:  # pragma: no cover
    faiss = None  # type: ignore
    FAISS_AVAILABLE = False


class IndexDimensionMismatch(RuntimeError):
    """저장된 인덱스와 현재 임베딩 모델의 차원이 다를 때 발생."""


class BaseVectorStore:
    backend = "base"

    def __init__(self, directory: Path, dimension: int, model_name: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.dimension = dimension
        self.model_name = model_name

    # -- 공통 메타 ---------------------------------------------------------
    @property
    def meta_path(self) -> Path:
        return self.directory / META_FILE

    def write_meta(self) -> None:
        self.meta_path.write_text(
            json.dumps(
                {
                    "backend": self.backend,
                    "dimension": self.dimension,
                    "model": self.model_name,
                    "count": self.count,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # -- 인터페이스 --------------------------------------------------------
    @property
    def count(self) -> int:
        raise NotImplementedError

    def add(self, ids: Sequence[int], vectors: np.ndarray) -> None:
        raise NotImplementedError

    def remove(self, ids: Sequence[int]) -> None:
        raise NotImplementedError

    def search(self, vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def save(self) -> None:
        raise NotImplementedError


class NumpyVectorStore(BaseVectorStore):
    backend = "numpy"

    def __init__(self, directory: Path, dimension: int, model_name: str) -> None:
        super().__init__(directory, dimension, model_name)
        self.vectors = np.zeros((0, dimension), dtype="float32")
        self.ids = np.zeros((0,), dtype="int64")
        self._load()

    def _load(self) -> None:
        vectors_path = self.directory / NUMPY_VECTORS
        ids_path = self.directory / NUMPY_IDS
        if vectors_path.exists() and ids_path.exists():
            vectors = np.load(vectors_path)
            ids = np.load(ids_path)
            if vectors.size and vectors.shape[1] != self.dimension:
                raise IndexDimensionMismatch(
                    f"저장된 인덱스 차원({vectors.shape[1]})과 현재 모델 차원"
                    f"({self.dimension})이 다릅니다. 전체 재색인이 필요합니다."
                )
            self.vectors = vectors.astype("float32")
            self.ids = ids.astype("int64")

    @property
    def count(self) -> int:
        return int(self.ids.shape[0])

    def add(self, ids: Sequence[int], vectors: np.ndarray) -> None:
        if len(ids) == 0:
            return
        vectors = np.asarray(vectors, dtype="float32")
        if vectors.shape[1] != self.dimension:
            raise IndexDimensionMismatch("추가하려는 벡터 차원이 인덱스와 다릅니다.")
        self.vectors = np.vstack([self.vectors, vectors]) if self.count else vectors
        self.ids = np.concatenate([self.ids, np.asarray(ids, dtype="int64")])

    def remove(self, ids: Sequence[int]) -> None:
        if not len(ids) or not self.count:
            return
        mask = ~np.isin(self.ids, np.asarray(ids, dtype="int64"))
        self.vectors = self.vectors[mask]
        self.ids = self.ids[mask]

    def search(self, vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        if not self.count:
            return []
        scores = self.vectors @ np.asarray(vector, dtype="float32")
        k = min(k, self.count)
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(self.ids[i]), float(scores[i])) for i in top]

    def reset(self) -> None:
        self.vectors = np.zeros((0, self.dimension), dtype="float32")
        self.ids = np.zeros((0,), dtype="int64")
        self.save()

    def save(self) -> None:
        np.save(self.directory / NUMPY_VECTORS, self.vectors)
        np.save(self.directory / NUMPY_IDS, self.ids)
        self.write_meta()


class FaissVectorStore(BaseVectorStore):  # pragma: no cover - faiss 설치 환경에서만
    backend = "faiss"

    def __init__(self, directory: Path, dimension: int, model_name: str) -> None:
        super().__init__(directory, dimension, model_name)
        path = self.directory / FAISS_FILE
        if path.exists():
            self.index = faiss.read_index(str(path))
            if self.index.d != dimension:
                raise IndexDimensionMismatch(
                    f"저장된 인덱스 차원({self.index.d})과 현재 모델 차원"
                    f"({dimension})이 다릅니다. 전체 재색인이 필요합니다."
                )
        else:
            self.index = faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))

    @property
    def count(self) -> int:
        return int(self.index.ntotal)

    def add(self, ids: Sequence[int], vectors: np.ndarray) -> None:
        if len(ids) == 0:
            return
        self.index.add_with_ids(
            np.asarray(vectors, dtype="float32"), np.asarray(ids, dtype="int64")
        )

    def remove(self, ids: Sequence[int]) -> None:
        if not len(ids):
            return
        self.index.remove_ids(np.asarray(ids, dtype="int64"))

    def search(self, vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        if not self.count:
            return []
        query = np.asarray(vector, dtype="float32").reshape(1, -1)
        scores, ids = self.index.search(query, min(k, self.count))
        return [
            (int(idx), float(score))
            for idx, score in zip(ids[0], scores[0])
            if idx != -1
        ]

    def reset(self) -> None:
        self.index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.dimension))
        self.save()

    def save(self) -> None:
        faiss.write_index(self.index, str(self.directory / FAISS_FILE))
        self.write_meta()


def open_store(
    dimension: int,
    model_name: str,
    directory: Path | None = None,
    prefer_faiss: bool = True,
) -> BaseVectorStore:
    """설치 환경에 맞는 Vector Store 를 연다(없으면 새로 만든다)."""
    directory = Path(directory or INDEX_DIR)
    directory.mkdir(parents=True, exist_ok=True)

    # 이미 만들어진 인덱스가 있으면 같은 backend 를 유지한다.
    backend = "faiss" if (FAISS_AVAILABLE and prefer_faiss) else "numpy"
    meta_path = directory / META_FILE
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            saved_backend = meta.get("backend", backend)
            if saved_backend == "faiss" and not FAISS_AVAILABLE:
                logger.warning("faiss index found but faiss is not installed")
            else:
                backend = saved_backend
        except json.JSONDecodeError:
            pass

    store_class = FaissVectorStore if backend == "faiss" else NumpyVectorStore
    return store_class(directory, dimension, model_name)


def index_meta(directory: Path | None = None) -> dict:
    """저장된 인덱스 메타(backend/dimension/model/count)를 읽는다."""
    path = Path(directory or INDEX_DIR) / META_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def index_model_name(directory: Path | None = None) -> str:
    """현재 인덱스가 어떤 임베딩 모델로 만들어졌는지 반환한다."""
    return str(index_meta(directory).get("model", ""))

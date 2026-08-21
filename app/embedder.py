"""로컬 Embedding 생성 (요구사항 4 - Embedding / Phase 3).

sentence-transformers 의 multilingual 모델을 로컬에서 실행한다.
외부 Embedding API는 사용하지 않으며, 모델 파일은 ``data/models`` 아래에
캐시된 것을 오프라인 모드로 읽는다.
"""

from __future__ import annotations

import hashlib
import os
from typing import Sequence

import numpy as np

from app.logging_setup import get_logger
from app.text_utils import tokenize

logger = get_logger("embed")

# 모델별 접두어 규칙(e5 계열은 query:/passage: 접두어가 필요하다)
PREFIX_RULES = {
    "e5": ("query: ", "passage: "),
    "bge": ("", ""),
    "ko-sbert": ("", ""),
}


class EmbeddingModelUnavailable(RuntimeError):
    """로컬 임베딩 모델을 불러올 수 없을 때 발생."""


class BaseEmbedder:
    name: str = "base"
    dimension: int = 0

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError

    def encode_query(self, text: str) -> np.ndarray:
        raise NotImplementedError


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype("float32")


class SentenceTransformerEmbedder(BaseEmbedder):
    """로컬 sentence-transformers 모델."""

    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        from app import netguard

        netguard.apply_offline_env(offline=True)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - 설치 안내용
            raise EmbeddingModelUnavailable(
                "sentence-transformers 가 설치되어 있지 않습니다.\n"
                "  pip install sentence-transformers"
            ) from exc

        from app.config import MODELS_DIR

        # local_files_only 는 버전에 따라 없을 수 있으므로 지원 여부를 확인한다.
        # (없는 경우에도 HF_HUB_OFFLINE=1 로 온라인 조회가 차단된다.)
        import inspect

        kwargs = {"cache_folder": str(MODELS_DIR)}
        if "local_files_only" in inspect.signature(SentenceTransformer.__init__).parameters:
            kwargs["local_files_only"] = True

        try:
            self.model = SentenceTransformer(model_name, **kwargs)
        except Exception as exc:
            raise EmbeddingModelUnavailable(
                f"로컬에 임베딩 모델('{model_name}')이 없습니다.\n"
                "  인터넷이 연결된 환경에서 아래 명령으로 한 번만 내려받으세요:\n"
                f"  python scripts/prepare_models.py --embedding {model_name}"
            ) from exc

        self.name = model_name
        self.batch_size = batch_size
        self.dimension = int(self.model.get_sentence_embedding_dimension())
        lowered = model_name.lower()
        self.query_prefix, self.passage_prefix = next(
            (value for key, value in PREFIX_RULES.items() if key in lowered), ("", "")
        )

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype="float32")
        prepared = [f"{self.passage_prefix}{text}" for text in texts]
        vectors = self.model.encode(
            prepared,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype="float32")

    def encode_query(self, text: str) -> np.ndarray:
        vectors = self.model.encode(
            [f"{self.query_prefix}{text}"],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype="float32")[0]


class HashingEmbedder(BaseEmbedder):
    """모델 파일 없이 동작하는 경량 대체 임베더.

    해시 기반 bag-of-tokens 벡터로, 의미 검색 품질은 낮지만
    (a) 자동화 테스트, (b) 모델 준비 전 기능 점검 용도로 사용한다.
    실제 사용 시에는 sentence-transformers 모델을 권장한다.
    """

    def __init__(self, dimension: int = 512) -> None:
        self.name = "hashing"
        self.dimension = dimension

    def _encode_one(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype="float32")
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return vector

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype="float32")
        return _normalize(np.vstack([self._encode_one(text) for text in texts]))

    def encode_query(self, text: str) -> np.ndarray:
        return _normalize(self._encode_one(text).reshape(1, -1))[0]


_cache: dict[str, BaseEmbedder] = {}


def get_embedder(model_name: str) -> BaseEmbedder:
    """임베더를 생성/캐시한다.

    환경변수 ``CHATBOT_EMBEDDER=hash`` 를 지정하면 모델 없이 동작하는
    HashingEmbedder 를 사용한다(테스트/점검용).
    """
    if os.environ.get("CHATBOT_EMBEDDER", "").lower() == "hash":
        return _cache.setdefault("hashing", HashingEmbedder())
    if model_name not in _cache:
        _cache[model_name] = SentenceTransformerEmbedder(model_name)
        logger.info(
            "embedding model loaded | model=%s dim=%s",
            model_name,
            _cache[model_name].dimension,
        )
    return _cache[model_name]


def clear_cache() -> None:
    _cache.clear()

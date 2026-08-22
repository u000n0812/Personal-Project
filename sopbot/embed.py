"""로컬 Embedding 생성.

외부 Embedding API는 사용하지 않는다. 다음 순서로 backend를 선택한다.

1. sentence-transformers (권장, multilingual 모델을 로컬에서 실행)
2. Ollama 로컬 Embedding (127.0.0.1, 예: bge-m3)
3. hashing (라이브러리가 전혀 없을 때 쓰는 최소 fallback, 검색 품질은 낮다)
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from typing import Iterable, Sequence

from .config import Settings
from .logging_setup import get_logger
from .security import assert_local_url

logger = get_logger("embed")

Vector = list[float]


class EmbeddingError(RuntimeError):
    """Embedding 생성에 실패했을 때 발생한다."""


def _l2_normalize(vector: Sequence[float]) -> Vector:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return list(vector)
    return [v / norm for v in vector]


class BaseEmbedder:
    name = "base"
    dimension = 0

    def encode_documents(self, texts: Sequence[str]) -> list[Vector]:
        raise NotImplementedError

    def encode_query(self, text: str) -> Vector:
        return self.encode_documents([text])[0]


class SentenceTransformerEmbedder(BaseEmbedder):
    """sentence-transformers 모델을 로컬에서 실행한다."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - 환경 의존
            raise EmbeddingError(
                "sentence-transformers가 설치되지 않았습니다. "
                "`pip install sentence-transformers` 후 사용하세요."
            ) from exc
        try:
            self._model = SentenceTransformer(model_name, device="cpu")
        except Exception as exc:  # 모델 파일이 로컬에 없을 때 포함
            raise EmbeddingError(
                f"Embedding 모델을 불러오지 못했습니다({model_name}). "
                "최초 1회 모델 준비가 필요합니다. README의 '모델 준비'를 참고하세요."
            ) from exc
        self.name = f"sentence-transformers:{model_name}"
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        # e5 계열 모델은 query/passage 접두어를 사용할 때 성능이 좋다.
        self._use_e5_prefix = "e5" in model_name.lower()

    def encode_documents(self, texts: Sequence[str]) -> list[Vector]:
        prepared = [f"passage: {t}" if self._use_e5_prefix else t for t in texts]
        vectors = self._model.encode(
            prepared, normalize_embeddings=True, batch_size=16, show_progress_bar=False
        )
        return [list(map(float, v)) for v in vectors]

    def encode_query(self, text: str) -> Vector:
        prepared = f"query: {text}" if self._use_e5_prefix else text
        vector = self._model.encode(
            [prepared], normalize_embeddings=True, show_progress_bar=False
        )[0]
        return list(map(float, vector))


class OllamaEmbedder(BaseEmbedder):
    """로컬 Ollama의 Embedding 기능을 사용한다(127.0.0.1 전용)."""

    def __init__(self, host: str, model: str, timeout: int = 120) -> None:
        self._url = assert_local_url(f"{host.rstrip('/')}/api/embeddings")
        self._model = model
        self._timeout = timeout
        self.name = f"ollama:{model}"
        probe = self._embed_one("dimension probe")
        self.dimension = len(probe)

    def _embed_one(self, text: str) -> Vector:
        payload = json.dumps({"model": self._model, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            # 로컬(127.0.0.1) 호출이므로 프록시를 사용하지 않는다.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise EmbeddingError(
                "로컬 Ollama Embedding 호출에 실패했습니다. Ollama 실행 상태를 확인하세요."
            ) from exc
        vector = data.get("embedding") or []
        if not vector:
            raise EmbeddingError(f"Embedding 결과가 비어 있습니다(model={self._model}).")
        return _l2_normalize([float(v) for v in vector])

    def encode_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed_one(t) for t in texts]


class HashingEmbedder(BaseEmbedder):
    """의존성이 전혀 없을 때 사용하는 fallback embedder.

    문자 n-gram을 해시해 벡터를 만든다. 모델 없이도 동작하지만
    의미 기반 검색 품질은 낮으므로 실제 운영에서는 권장하지 않는다.
    """

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension
        self.name = f"hashing:{dimension}"

    @staticmethod
    def _features(text: str) -> Iterable[str]:
        lowered = text.lower()
        for word in re.findall(r"[0-9a-z]+|[가-힣]+", lowered):
            yield word
            if len(word) > 1:
                for i in range(len(word) - 1):
                    yield word[i : i + 2]

    def encode_documents(self, texts: Sequence[str]) -> list[Vector]:
        vectors: list[Vector] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for feature in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            vectors.append(_l2_normalize(vector))
        return vectors


def get_embedder(settings: Settings) -> BaseEmbedder:
    """설정에 따라 Embedding backend를 선택한다."""
    backend = (settings.embed_backend or "auto").lower()

    if backend in ("sentence-transformers", "st"):
        return SentenceTransformerEmbedder(settings.embed_model)
    if backend == "ollama":
        return OllamaEmbedder(settings.ollama_host, settings.ollama_embed_model)
    if backend == "hashing":
        return HashingEmbedder()

    # auto: 사용 가능한 것을 순서대로 시도한다.
    for factory, label in (
        (lambda: SentenceTransformerEmbedder(settings.embed_model), "sentence-transformers"),
        (lambda: OllamaEmbedder(settings.ollama_host, settings.ollama_embed_model), "ollama"),
    ):
        try:
            embedder = factory()
            logger.info("embedder selected: %s", label)
            return embedder
        except EmbeddingError as exc:
            logger.warning("embedder unavailable (%s): %s", label, exc.__class__.__name__)
    logger.warning("embedder fallback: hashing (검색 품질이 낮습니다)")
    return HashingEmbedder()

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

    @property
    def suggested_threshold(self) -> float:
        """모델별 권장 vector 유사도 threshold.

        모델마다 cosine 유사도 분포가 달라 하나의 고정값을 쓸 수 없다.
        설정에서 threshold를 0(자동)으로 두면 이 값이 사용된다.
        """
        return 0.4

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
        self._model_name = model_name.lower()

    @property
    def suggested_threshold(self) -> float:
        if "e5" in self._model_name:
            return 0.80    # e5 계열은 무관한 문장도 0.7대가 나온다
        if "bge-m3" in self._model_name:
            return 0.50
        return 0.45

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


def _mentions_model(error: "urllib.error.HTTPError") -> bool:
    """404 응답이 '엔드포인트 없음'이 아니라 '모델 없음'인지 판단한다."""
    try:
        body = error.read().decode("utf-8", errors="replace").lower()
    except Exception:
        return False
    return "model" in body


class OllamaEmbedder(BaseEmbedder):
    """로컬 Ollama의 Embedding 모델을 사용한다(127.0.0.1 전용).

    권장 모델은 bge-m3 이다(한국어/영문 혼용 문서에 강하고 1024차원).
    Ollama 버전에 따라 두 가지 API가 있어 자동으로 선택한다.
      - /api/embed      : 여러 문장을 한 번에 처리(최신, 빠름)
      - /api/embeddings : 한 문장씩 처리(구버전 호환)
    """

    BATCH_SIZE = 16

    def __init__(self, host: str, model: str, timeout: int = 300) -> None:
        base = host.rstrip("/")
        self._batch_url = assert_local_url(f"{base}/api/embed")
        self._single_url = assert_local_url(f"{base}/api/embeddings")
        self._model = model
        self._timeout = timeout
        self.name = f"ollama:{model}"
        # 로컬(127.0.0.1) 호출이므로 시스템 프록시를 사용하지 않는다.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._use_batch = True
        probe = self.encode_documents(["차원 확인"])
        self.dimension = len(probe[0])
        logger.info("ollama embedder ready: model=%s dim=%d batch=%s",
                    model, self.dimension, self._use_batch)

    @property
    def suggested_threshold(self) -> float:
        # bge-m3 계열은 관련 문서 0.6~0.8, 무관한 문서 0.3~0.45 수준으로 분포한다.
        return 0.5

    # ------------------------------------------------------------------
    def _post(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self._opener.open(request, timeout=self._timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _embed_batch(self, texts: Sequence[str]) -> list[Vector]:
        data = self._post(self._batch_url, {"model": self._model, "input": list(texts)})
        vectors = data.get("embeddings") or []
        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"Embedding 개수가 요청과 다릅니다(요청 {len(texts)}, 응답 {len(vectors)})."
            )
        return [_l2_normalize([float(v) for v in vector]) for vector in vectors]

    def _embed_one(self, text: str) -> Vector:
        data = self._post(self._single_url, {"model": self._model, "prompt": text})
        vector = data.get("embedding") or []
        if not vector:
            raise EmbeddingError(f"Embedding 결과가 비어 있습니다(model={self._model}).")
        return _l2_normalize([float(v) for v in vector])

    def encode_documents(self, texts: Sequence[str]) -> list[Vector]:
        if not texts:
            return []
        vectors: list[Vector] = []
        try:
            for start in range(0, len(texts), self.BATCH_SIZE):
                block = list(texts[start : start + self.BATCH_SIZE])
                if self._use_batch:
                    try:
                        vectors.extend(self._embed_batch(block))
                        continue
                    except urllib.error.HTTPError as exc:
                        if exc.code != 404 or _mentions_model(exc):
                            raise
                        # 구버전 Ollama: /api/embed 가 없으므로 단건 API로 전환한다.
                        logger.info("ollama /api/embed unavailable -> fallback to /api/embeddings")
                        self._use_batch = False
                vectors.extend(self._embed_one(text) for text in block)
        except EmbeddingError:
            raise
        except urllib.error.HTTPError as exc:
            raise EmbeddingError(
                f"로컬 Ollama Embedding 오류(HTTP {exc.code}). "
                f"모델이 설치되어 있는지 확인하세요: ollama pull {self._model}"
            ) from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise EmbeddingError(
                "로컬 Ollama Embedding 호출에 실패했습니다. Ollama 실행 상태를 확인하세요 "
                "(터미널에서 `ollama serve`)."
            ) from exc
        return vectors


class HashingEmbedder(BaseEmbedder):
    """의존성이 전혀 없을 때 사용하는 fallback embedder.

    문자 n-gram을 해시해 벡터를 만든다. 모델 없이도 동작하지만
    의미 기반 검색 품질은 낮으므로 실제 운영에서는 권장하지 않는다.
    """

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension
        self.name = f"hashing:{dimension}"

    @property
    def suggested_threshold(self) -> float:
        return 0.30   # 의미 기반이 아니므로 유사도 값 자체가 낮게 나온다

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
    # Ollama(bge-m3)를 먼저 시도한다. 이미 설치된 Ollama를 그대로 쓰므로
    # torch 설치가 필요 없고, 한국어 지침문서 검색 품질도 충분하다.
    for factory, label in (
        (lambda: OllamaEmbedder(settings.ollama_host, settings.ollama_embed_model), "ollama"),
        (lambda: SentenceTransformerEmbedder(settings.embed_model), "sentence-transformers"),
    ):
        try:
            embedder = factory()
            logger.info("embedder selected: %s", label)
            return embedder
        except EmbeddingError as exc:
            logger.warning("embedder unavailable (%s): %s", label, exc.__class__.__name__)
    logger.warning("embedder fallback: hashing (검색 품질이 낮습니다)")
    return HashingEmbedder()

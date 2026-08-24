"""프로그램 구성 요소를 하나로 묶는 서비스 계층.

CLI(cli.py)와 Streamlit UI(app.py)가 동일한 객체 구성을 사용하도록 한다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from .config import CONFIG_PATH, DATA_DIR, INDEX_DIR, Settings, ensure_dirs
from .db import STATUS_ACTIVE, STATUS_DISABLED, STATUS_SUPERSEDED, Database
from .embed import BaseEmbedder, get_embedder
from .extract import pdf_crypto_backend
from .ingest import DocumentIngestor, IngestResult
from .llm import OllamaClient
from .logging_setup import get_logger
from .rag import RagAnswer, RagEngine
from .search import Retriever
from .vectorstore import VectorStore

logger = get_logger("service")


@dataclass
class HealthReport:
    """실행 환경 점검 결과(Phase 1 / Phase 9 확인용)."""

    data_dir: str
    llm_host: str
    llm_available: bool
    llm_models: list[str]
    llm_model_ready: bool
    embedder_name: str
    embedder_dimension: int
    index_backend: str
    index_vectors: int
    index_embedder: str
    embedding_model_changed: bool
    documents: int
    active_documents: int
    chunks: int
    pdf_crypto_backend: str
    python_executable: str

    def as_lines(self) -> list[str]:
        return [
            f"Python 실행 파일   : {self.python_executable}",
            f"데이터 폴더        : {self.data_dir}",
            f"로컬 LLM 주소      : {self.llm_host}",
            f"로컬 LLM 연결      : {'연결됨' if self.llm_available else '연결 안 됨 (ollama serve 확인)'}",
            f"설치된 모델        : {', '.join(self.llm_models) if self.llm_models else '없음'}",
            f"선택 모델 사용가능 : {'예' if self.llm_model_ready else '아니오'}",
            f"Embedding backend  : {self.embedder_name} (dim={self.embedder_dimension})",
            f"Vector Index       : {self.index_backend}, {self.index_vectors}개 vector",
            f"Index Embedding    : {self.index_embedder or '(없음)'}",
            f"모델 변경 감지     : {'예 → 전체 재색인 필요' if self.embedding_model_changed else '아니오'}",
            f"등록 문서          : {self.documents}개 (활성 {self.active_documents}개)",
            f"Chunk 수           : {self.chunks}개",
            f"PDF 암호화 처리    : {self.pdf_crypto_backend}",
        ]


class AppService:
    """설정 → DB → Index → Embedder → 검색 → RAG 로 이어지는 구성 요소 컨테이너."""

    def __init__(self, settings: Settings | None = None) -> None:
        ensure_dirs()
        self.settings = settings or Settings.load()
        self._db: Database | None = None
        self._store: VectorStore | None = None
        self._embedder: BaseEmbedder | None = None
        self._retriever: Retriever | None = None
        self._engine: RagEngine | None = None
        self._ingestor: DocumentIngestor | None = None
        self._client: OllamaClient | None = None

    # ------------------------------------------------------------------
    # 구성 요소 (필요할 때 생성)
    # ------------------------------------------------------------------
    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database()
        return self._db

    @property
    def store(self) -> VectorStore:
        if self._store is None:
            self._store = VectorStore(INDEX_DIR)
        return self._store

    @property
    def embedder(self) -> BaseEmbedder:
        if self._embedder is None:
            self._embedder = get_embedder(self.settings)
        return self._embedder

    @property
    def client(self) -> OllamaClient:
        if self._client is None:
            self._client = OllamaClient(self.settings.ollama_host, self.settings.llm_timeout_sec)
        return self._client

    @property
    def retriever(self) -> Retriever:
        if self._retriever is None:
            self._retriever = Retriever(self.db, self.store, self.embedder, self.settings)
        return self._retriever

    @property
    def engine(self) -> RagEngine:
        if self._engine is None:
            self._engine = RagEngine(self.retriever, self.client, self.settings)
        return self._engine

    @property
    def ingestor(self) -> DocumentIngestor:
        if self._ingestor is None:
            self._ingestor = DocumentIngestor(self.db, self.store, self.embedder, self.settings)
        return self._ingestor

    # ------------------------------------------------------------------
    # 동작
    # ------------------------------------------------------------------
    def apply_settings(self, settings: Settings) -> None:
        """Settings 화면에서 값이 바뀌면 관련 구성 요소를 다시 만든다."""
        embedding_changed = (
            settings.embed_backend != self.settings.embed_backend
            or settings.embed_model != self.settings.embed_model
            or settings.ollama_embed_model != self.settings.ollama_embed_model
        )
        host_changed = settings.ollama_host != self.settings.ollama_host
        self.settings = settings
        settings.save(CONFIG_PATH)
        if embedding_changed:
            self._embedder = None
            self._retriever = None
            self._engine = None
            self._ingestor = None
        if host_changed:
            self._client = None
            self._engine = None
        if self._retriever is not None:
            self._retriever.settings = settings
            self._retriever.invalidate()
        if self._engine is not None:
            self._engine.settings = settings
        if self._ingestor is not None:
            self._ingestor.settings = settings

    def register(self, paths: Sequence[Path | str]) -> list[IngestResult]:
        results = self.ingestor.register_paths(paths)
        self.retriever.invalidate()
        return results

    def ask(self, question: str, history: Sequence[tuple[str, str]] = ()) -> RagAnswer:
        return self.engine.answer(question, history)

    def health(self) -> HealthReport:
        models = self.client.list_models() if self.client.is_available() else []
        selected = self.settings.llm_model
        model_ready = any(
            m == selected or m.split(":")[0] == selected.split(":")[0] for m in models
        )
        try:
            embedder = self.embedder
            embedder_name, dimension = embedder.name, embedder.dimension
        except Exception as exc:  # 모델 준비 전에도 진단은 가능해야 한다.
            embedder_name, dimension = f"사용 불가 ({exc.__class__.__name__})", 0
        stats = self.db.stats()
        crypto = pdf_crypto_backend()
        if crypto is None:
            pdf_crypto_label = "확인 불가 (pypdf 미설치)"
        elif crypto[0] == "local_crypt_fallback":
            pdf_crypto_label = (
                "cryptography 없음 - 암호화된 PDF를 열 수 없습니다 "
                "(pip install cryptography 후 프로그램을 완전히 재시작하세요)"
            )
        else:
            pdf_crypto_label = f"{crypto[0]} {crypto[1]} (정상)"
        return HealthReport(
            data_dir=str(DATA_DIR),
            llm_host=self.settings.ollama_host,
            llm_available=self.client.is_available(),
            llm_models=models,
            llm_model_ready=model_ready,
            embedder_name=embedder_name,
            embedder_dimension=dimension,
            index_backend=self.store.backend,
            index_vectors=len(self.store),
            index_embedder=self.store.embedder_name,
            embedding_model_changed=self.ingestor.embedding_model_changed(),
            documents=stats["documents"],
            active_documents=stats["active_documents"],
            chunks=stats["chunks"],
            pdf_crypto_backend=pdf_crypto_label,
            python_executable=sys.executable,
        )

    def documents(self, include_all: bool = True):
        statuses = (
            (STATUS_ACTIVE, STATUS_SUPERSEDED, STATUS_DISABLED) if include_all else (STATUS_ACTIVE,)
        )
        return self.db.list_documents(statuses)

    @property
    def llm_port(self) -> int:
        return urlparse(self.settings.ollama_host).port or 11434

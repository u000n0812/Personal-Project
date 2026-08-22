"""문서 등록 파이프라인.

텍스트 추출 → 구조 분석 → Chunk 분할 → Embedding → Vector Index 저장 → Metadata 저장
순서로 처리한다. 같은 문서의 새 버전이 들어오면 과거 버전을 덮어쓰지 않고
'superseded'로 표시하여 이력을 남긴다.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .chunk import build_embedding_text, chunk_blocks
from .config import DOCUMENTS_DIR, Settings, ensure_dirs
from .db import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_SUPERSEDED,
    Database,
    Document,
)
from .embed import BaseEmbedder, EmbeddingError
from .extract import SUPPORTED_EXTENSIONS, ExtractionError, extract_document
from .logging_setup import get_logger
from .naming import is_newer_version, parse_doc_name, version_sort_key
from .search import INDEX_VERSION_KEY
from .vectorstore import VectorStore

logger = get_logger("ingest")


@dataclass
class IngestResult:
    """문서 1건 처리 결과 (로그와 UI 표시에 사용)."""

    file_name: str
    status: str          # added | duplicate | replaced_version | error | skipped
    message: str = ""
    document_id: int | None = None
    chunk_count: int = 0

    @property
    def ok(self) -> bool:
        return self.status in ("added", "replaced_version")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_file_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", name).strip("_")
    return cleaned or "document"


class DocumentIngestor:
    """문서 등록 / 재색인 / 삭제를 담당한다."""

    def __init__(
        self,
        db: Database,
        store: VectorStore,
        embedder: BaseEmbedder,
        settings: Settings,
    ) -> None:
        ensure_dirs()
        self.db = db
        self.store = store
        self.embedder = embedder
        self.settings = settings

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------
    def _bump_index_version(self) -> None:
        current = int(self.db.get_meta(INDEX_VERSION_KEY, "0") or 0)
        self.db.set_meta(INDEX_VERSION_KEY, str(current + 1))

    def _embed_chunks(self, rows: Sequence[dict], document: Document) -> list[list[float]]:
        texts = [
            build_embedding_text(row, doc_title=document.title, version=document.version)
            for row in rows
        ]
        return self.embedder.encode_documents(texts)

    def _apply_version_policy(self, document: Document) -> str:
        """같은 doc_key의 다른 버전과 비교해 활성 상태를 정리한다."""
        siblings = [d for d in self.db.documents_by_key(document.doc_key) if d.id != document.id]
        if not siblings:
            return STATUS_ACTIVE
        newest_other = max(siblings, key=lambda d: version_sort_key(d.version))
        for other in siblings:
            if other.status == STATUS_DISABLED:
                continue
            if is_newer_version(document.version, other.version):
                self.db.set_status(other.id, STATUS_SUPERSEDED)
        if any(
            is_newer_version(other.version, document.version)
            for other in siblings
            if other.status != STATUS_DISABLED
        ):
            self.db.set_status(document.id, STATUS_SUPERSEDED)
            logger.info(
                "document %s registered as older version (newest=%s)",
                document.id,
                newest_other.version,
            )
            return STATUS_SUPERSEDED
        return STATUS_ACTIVE

    # ------------------------------------------------------------------
    # 등록
    # ------------------------------------------------------------------
    def register_file(self, path: Path | str) -> IngestResult:
        path = Path(path)
        if not path.exists() or not path.is_file():
            return IngestResult(path.name, "error", "파일을 찾을 수 없습니다.")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return IngestResult(path.name, "skipped", f"지원하지 않는 형식({path.suffix})")

        file_hash = file_sha256(path)
        existing = self.db.get_document_by_hash(file_hash)
        if existing:
            return IngestResult(
                path.name,
                "duplicate",
                f"내용이 동일한 문서가 이미 등록되어 있습니다(ID {existing.id}).",
                document_id=existing.id,
                chunk_count=existing.chunk_count,
            )

        try:
            extracted = extract_document(path)
        except ExtractionError as exc:
            logger.error("extract failed: file=%s code=%s", safe_file_name(path.name), exc.__class__.__name__)
            return IngestResult(path.name, "error", str(exc))

        doc_key, version, title = parse_doc_name(path.name)
        chunks = chunk_blocks(
            extracted.blocks,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
            doc_title=title,
        )
        if not chunks:
            return IngestResult(path.name, "error", "문서에서 사용할 수 있는 내용을 찾지 못했습니다.")

        stored_path = DOCUMENTS_DIR / f"{file_hash[:10]}_{safe_file_name(path.name)}"
        try:
            shutil.copy2(path, stored_path)
        except OSError as exc:
            return IngestResult(path.name, "error", f"문서 사본 저장 실패: {exc.__class__.__name__}")

        document_id = self.db.insert_document(
            doc_key=doc_key,
            title=title,
            file_name=path.name,
            version=version,
            ext=path.suffix.lower(),
            file_hash=file_hash,
            source_path=str(path.resolve()),
            stored_path=str(stored_path),
            page_count=extracted.page_count,
        )
        document = self.db.get_document(document_id)
        assert document is not None

        rows = [c.as_row() for c in chunks]
        chunk_ids = self.db.replace_chunks(document_id, rows)

        try:
            vectors = self._embed_chunks(rows, document)
        except EmbeddingError as exc:
            # Embedding 실패 시 등록을 취소해 반쪽 상태를 남기지 않는다.
            self.db.delete_document(document_id)
            stored_path.unlink(missing_ok=True)
            logger.error("embedding failed: file=%s", safe_file_name(path.name))
            return IngestResult(path.name, "error", str(exc))

        self.store.embedder_name = self.embedder.name
        self.store.add(chunk_ids, vectors)
        self.store.save()

        status = self._apply_version_policy(document)
        self._bump_index_version()
        logger.info(
            "document registered: id=%s chunks=%d status=%s", document_id, len(chunk_ids), status
        )

        note = "등록 완료"
        if status == STATUS_SUPERSEDED:
            note = "등록되었지만 더 최신 버전이 있어 과거 버전으로 표시됩니다."
        elif len(self.db.documents_by_key(doc_key)) > 1:
            note = "등록 완료 (이전 버전은 과거 버전으로 전환됨)"
            return IngestResult(path.name, "replaced_version", note, document_id, len(chunk_ids))
        return IngestResult(path.name, "added", note, document_id, len(chunk_ids))

    def register_paths(self, paths: Iterable[Path | str], recursive: bool = True) -> list[IngestResult]:
        """파일과 폴더를 함께 받아 등록한다."""
        results: list[IngestResult] = []
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                pattern = "**/*" if recursive else "*"
                for child in sorted(path.glob(pattern)):
                    if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                        results.append(self.register_file(child))
            else:
                results.append(self.register_file(path))
        return results

    # ------------------------------------------------------------------
    # 재색인 / 삭제 / 상태 변경
    # ------------------------------------------------------------------
    def reindex(self, document_id: int) -> IngestResult:
        document = self.db.get_document(document_id)
        if document is None:
            return IngestResult(str(document_id), "error", "문서를 찾을 수 없습니다.")
        source = Path(document.stored_path)
        if not source.exists():
            source = Path(document.source_path)
        if not source.exists():
            return IngestResult(document.file_name, "error", "원본 파일을 찾을 수 없습니다.")

        old_chunk_ids = self.db.chunk_ids_for_document(document_id)
        try:
            extracted = extract_document(source)
        except ExtractionError as exc:
            return IngestResult(document.file_name, "error", str(exc))

        chunks = chunk_blocks(
            extracted.blocks,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
            doc_title=document.title,
        )
        rows = [c.as_row() for c in chunks]
        self.store.remove(old_chunk_ids)
        chunk_ids = self.db.replace_chunks(document_id, rows)
        try:
            vectors = self._embed_chunks(rows, document)
        except EmbeddingError as exc:
            self.store.save()
            return IngestResult(document.file_name, "error", str(exc))
        self.store.embedder_name = self.embedder.name
        self.store.add(chunk_ids, vectors)
        self.store.save()
        self._bump_index_version()
        logger.info("document reindexed: id=%s chunks=%d", document_id, len(chunk_ids))
        return IngestResult(document.file_name, "added", "재색인 완료", document_id, len(chunk_ids))

    def delete(self, document_id: int) -> IngestResult:
        """문서와 관련된 모든 데이터를 삭제한다(목록에서만 지우지 않는다)."""
        document = self.db.get_document(document_id)
        if document is None:
            return IngestResult(str(document_id), "error", "문서를 찾을 수 없습니다.")

        chunk_ids = self.db.chunk_ids_for_document(document_id)
        removed = self.store.remove(chunk_ids)   # Vector 삭제
        self.store.save()
        self.db.delete_document(document_id)     # Metadata + chunk 텍스트 삭제
        Path(document.stored_path).unlink(missing_ok=True)  # 문서 사본 삭제

        # 남은 버전 중 가장 최신을 다시 활성화한다.
        siblings = [d for d in self.db.documents_by_key(document.doc_key) if d.status != STATUS_DISABLED]
        if siblings:
            newest = siblings[0]
            for candidate in siblings[1:]:
                if is_newer_version(candidate.version, newest.version):
                    newest = candidate
            if newest.status != STATUS_ACTIVE:
                self.db.set_status(newest.id, STATUS_ACTIVE)

        self._bump_index_version()
        logger.info("document deleted: id=%s vectors=%d", document_id, removed)
        return IngestResult(document.file_name, "added", "삭제 완료", document_id, 0)

    def set_status(self, document_id: int, status: str) -> IngestResult:
        document = self.db.get_document(document_id)
        if document is None:
            return IngestResult(str(document_id), "error", "문서를 찾을 수 없습니다.")
        self.db.set_status(document_id, status)
        self._bump_index_version()
        return IngestResult(document.file_name, "added", f"상태 변경: {status}", document_id)

    # ------------------------------------------------------------------
    # 전체 재색인 (Embedding 모델 변경 시)
    # ------------------------------------------------------------------
    def embedding_model_changed(self) -> bool:
        return bool(self.store.embedder_name) and self.store.embedder_name != self.embedder.name

    def rebuild_index(self) -> int:
        """DB에 저장된 chunk 텍스트로 Vector Index만 다시 만든다."""
        rows = self.db.iter_chunks_for_search((STATUS_ACTIVE, STATUS_SUPERSEDED, STATUS_DISABLED))
        self.store.reset(embedder_name=self.embedder.name, dimension=0)
        self.store.dimension = 0
        if not rows:
            self.store.save()
            self._bump_index_version()
            return 0
        texts = [
            build_embedding_text(
                {"heading_path": c.heading_path, "text": c.text, "section": c.section},
                doc_title=d.title,
                version=d.version,
            )
            for c, d in rows
        ]
        vectors = self.embedder.encode_documents(texts)
        self.store.embedder_name = self.embedder.name
        self.store.add([c.id for c, _ in rows], vectors)
        self.store.save()
        self._bump_index_version()
        logger.info("index rebuilt: chunks=%d", len(rows))
        return len(rows)

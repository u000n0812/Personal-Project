"""문서 등록/삭제/재색인 파이프라인 (요구사항 6, 7, 18 / Phase 3, 8).

등록 순서:
  텍스트 추출 → 구조 분석 → Chunk 분할 → Embedding → Vector Index → Metadata

삭제 시에는 원본 파일 / Chunk(추출 Text) / Embedding / Vector / Metadata 를
모두 제거한다(요구사항 18).
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from app import db, versioning
from app.chunker import chunk_blocks
from app.config import (
    DOCUMENTS_DIR,
    SUPPORTED_EXTENSIONS,
    Settings,
    ensure_directories,
)
from app.embedder import get_embedder
from app.extractors import UnsupportedDocument, extract
from app.keyword import build_from_rows
from app.logging_setup import get_logger
from app.vectorstore import index_meta, open_store

logger = get_logger("pipeline")

STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"


@dataclass
class IngestResult:
    filename: str
    status: str  # indexed | replaced | skipped | failed
    document_id: int | None = None
    chunk_count: int = 0
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("indexed", "replaced", "skipped")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "document"


class DocumentIndex:
    """문서 색인 전체를 관리하는 진입점."""

    def __init__(self, settings: Settings) -> None:
        ensure_directories()
        db.init_db()
        self.settings = settings
        self._embedder = None
        self._store = None
        self._bm25 = None
        self._bm25_generation = -1

    # ------------------------------------------------------------- 리소스
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_embedder(self.settings.embedding_model)
        return self._embedder

    @property
    def store(self):
        """Vector Store. 이미 만들어진 인덱스가 있으면 임베딩 모델을 메모리에
        올리지 않고도 열 수 있다(문서 목록 조회 등 가벼운 작업용)."""
        if self._store is None:
            meta = index_meta()
            if meta.get("dimension") and meta.get("model") == self.settings.embedding_model:
                self._store = open_store(int(meta["dimension"]), str(meta["model"]))
            else:
                self._store = open_store(self.embedder.dimension, self.embedder.name)
        return self._store

    def _generation(self) -> int:
        with db.connect() as conn:
            return int(db.get_meta(conn, "generation", "0") or 0)

    def _bump_generation(self, conn) -> None:
        current = int(db.get_meta(conn, "generation", "0") or 0)
        db.set_meta(conn, "generation", str(current + 1))

    @property
    def bm25(self):
        """활성 문서 기준 BM25 인덱스(변경이 있을 때만 재구축)."""
        generation = self._generation()
        if self._bm25 is None or generation != self._bm25_generation:
            with db.connect() as conn:
                rows = db.iter_active_chunks(conn)
            self._bm25 = build_from_rows(rows)
            self._bm25_generation = generation
            logger.info("keyword index rebuilt | chunks=%s", self._bm25.size)
        return self._bm25

    # ------------------------------------------------------------- 조회
    def documents(self, only_active: bool = False) -> list:
        with db.connect() as conn:
            return db.list_documents(conn, only_active=only_active)

    def stats(self) -> dict:
        with db.connect() as conn:
            info = db.stats(conn)
        try:
            info["vectors"] = self.store.count
            info["backend"] = self.store.backend
        except Exception:
            # 아직 인덱스가 없고 임베딩 모델도 준비되지 않은 상태
            info["vectors"] = 0
            info["backend"] = "미생성"
        return info

    # ------------------------------------------------------------- 등록
    def ingest_file(self, path: str | Path, *, force: bool = False) -> IngestResult:
        path = Path(path)
        filename = path.name
        if not path.exists():
            return IngestResult(filename, "failed", message="파일을 찾을 수 없습니다.")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return IngestResult(
                filename, "failed", message=f"지원하지 않는 형식입니다({path.suffix})."
            )

        try:
            checksum = sha256_of(path)
        except OSError as exc:
            logger.error("hash failed | file_error=%s", type(exc).__name__)
            return IngestResult(filename, "failed", message="파일을 읽을 수 없습니다.")

        info = versioning.describe(filename)

        # 이미 동일한 내용의 문서가 등록되어 있으면 다시 임베딩하지 않는다(요구사항 20).
        with db.connect() as conn:
            existing = db.get_document_by_sha(conn, checksum)
            same_version = next(
                (
                    row
                    for row in db.list_versions(conn, info["doc_key"])
                    if row["version"] == info["version"] and row["sha256"] != checksum
                ),
                None,
            )
        if existing and not force:
            return IngestResult(
                filename,
                "skipped",
                document_id=int(existing["id"]),
                chunk_count=int(existing["chunk_count"]),
                message="이미 등록된 문서입니다(내용 변경 없음).",
            )
        if existing and force:
            return self.reindex_document(int(existing["id"]))

        replaced = False
        if same_version is not None:
            # 같은 버전인데 내용이 바뀐 경우 = 문서 교체
            self.delete_document(int(same_version["id"]))
            replaced = True

        # 1) 텍스트 추출 -----------------------------------------------------
        try:
            extracted = extract(path)
        except UnsupportedDocument as exc:
            logger.warning("extract failed | ext=%s", path.suffix)
            return IngestResult(filename, "failed", message=str(exc))
        except Exception as exc:  # pragma: no cover - 손상 파일 방어
            logger.error("extract error | error=%s", type(exc).__name__)
            return IngestResult(
                filename, "failed", message=f"문서를 읽는 중 오류가 발생했습니다({type(exc).__name__})."
            )

        # 2) Chunk 분할 -------------------------------------------------------
        chunks = chunk_blocks(
            extracted.blocks,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        if not chunks:
            return IngestResult(filename, "failed", message="추출된 본문이 없습니다.")

        # 3) Embedding --------------------------------------------------------
        vectors = self.embedder.encode_passages([chunk["text"] for chunk in chunks])

        # 4) 저장 --------------------------------------------------------------
        stored_path = DOCUMENTS_DIR / f"{checksum[:12]}_{_safe_filename(filename)}"
        chunk_ids: list[int] = []
        try:
            shutil.copy2(path, stored_path)
            with db.connect() as conn:
                document_id = db.insert_document(
                    conn,
                    doc_key=info["doc_key"],
                    title=info["title"] or extracted.title,
                    filename=filename,
                    version=info["version"],
                    version_key=info["version_key"],
                    ext=path.suffix.lower(),
                    sha256=checksum,
                    stored_path=str(stored_path),
                    source_path=str(path.resolve()),
                    page_count=extracted.page_count,
                )
                chunk_ids = db.insert_chunks(conn, document_id, chunks)
                self.store.add(chunk_ids, vectors)
                self._apply_version_policy(conn, info["doc_key"])
                self._bump_generation(conn)
            self.store.save()
        except Exception as exc:
            if chunk_ids:
                self.store.remove(chunk_ids)
            stored_path.unlink(missing_ok=True)
            logger.error("ingest failed | error=%s", type(exc).__name__)
            return IngestResult(
                filename, "failed", message=f"등록 중 오류가 발생했습니다({type(exc).__name__})."
            )

        logger.info(
            "document indexed | doc_id=%s chunks=%s status=%s",
            document_id,
            len(chunk_ids),
            "replaced" if replaced else "indexed",
        )
        return IngestResult(
            filename,
            "replaced" if replaced else "indexed",
            document_id=document_id,
            chunk_count=len(chunk_ids),
            message=(
                "같은 버전의 기존 문서를 새 내용으로 교체했습니다."
                if replaced
                else "등록이 완료되었습니다."
            ),
        )

    def ingest_paths(
        self, paths: Iterable[str | Path], *, force: bool = False
    ) -> list[IngestResult]:
        return [self.ingest_file(path, force=force) for path in paths]

    def ingest_folder(
        self, folder: str | Path, *, recursive: bool = True, force: bool = False
    ) -> list[IngestResult]:
        folder = Path(folder)
        if not folder.is_dir():
            return [IngestResult(str(folder), "failed", message="폴더를 찾을 수 없습니다.")]
        pattern = "**/*" if recursive else "*"
        files = sorted(
            path
            for path in folder.glob(pattern)
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        return self.ingest_paths(files, force=force)

    # ------------------------------------------------------------- 버전 정책
    def _apply_version_policy(self, conn, doc_key: str) -> None:
        """같은 doc_key 중 최신 버전만 활성 상태로 유지한다(요구사항 7)."""
        rows = db.list_versions(conn, doc_key)
        if len(rows) <= 1:
            return
        newest = max(rows, key=lambda row: (row["version_key"], row["id"]))
        for row in rows:
            desired = STATUS_ACTIVE if row["id"] == newest["id"] else STATUS_INACTIVE
            if row["status"] != desired:
                db.update_document(conn, int(row["id"]), status=desired)

    # ------------------------------------------------------------- 관리
    def set_status(self, document_id: int, active: bool) -> None:
        with db.connect() as conn:
            db.update_document(
                conn, document_id, status=STATUS_ACTIVE if active else STATUS_INACTIVE
            )
            self._bump_generation(conn)

    def reindex_document(self, document_id: int) -> IngestResult:
        """저장된 원본 파일로 다시 추출/임베딩한다."""
        with db.connect() as conn:
            row = db.get_document(conn, document_id)
        if row is None:
            return IngestResult("", "failed", message="문서를 찾을 수 없습니다.")

        stored_path = Path(row["stored_path"])
        if not stored_path.exists():
            return IngestResult(
                row["filename"], "failed", message="저장된 원본 파일이 없습니다."
            )

        try:
            extracted = extract(stored_path)
        except Exception as exc:
            logger.error("reindex extract failed | doc_id=%s error=%s", document_id, type(exc).__name__)
            return IngestResult(row["filename"], "failed", message=str(exc))

        chunks = chunk_blocks(
            extracted.blocks,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        if not chunks:
            return IngestResult(row["filename"], "failed", message="추출된 본문이 없습니다.")

        vectors = self.embedder.encode_passages([chunk["text"] for chunk in chunks])

        with db.connect() as conn:
            old_ids = db.delete_chunks(conn, document_id)
            self.store.remove(old_ids)
            new_ids = db.insert_chunks(conn, document_id, chunks)
            self.store.add(new_ids, vectors)
            db.update_document(conn, document_id, page_count=extracted.page_count)
            self._bump_generation(conn)
        self.store.save()

        logger.info("document reindexed | doc_id=%s chunks=%s", document_id, len(new_ids))
        return IngestResult(
            row["filename"],
            "indexed",
            document_id=document_id,
            chunk_count=len(new_ids),
            message="재색인이 완료되었습니다.",
        )

    def delete_document(self, document_id: int) -> bool:
        """원본 파일 + 추출 Text + Embedding + Vector + Metadata 전체 삭제."""
        with db.connect() as conn:
            row = db.get_document(conn, document_id)
            if row is None:
                return False
            chunk_ids = db.get_chunk_ids(conn, document_id)
            self.store.remove(chunk_ids)
            db.delete_document_row(conn, document_id)
            self._apply_version_policy(conn, row["doc_key"])
            self._bump_generation(conn)
        self.store.save()

        stored_path = Path(row["stored_path"])
        try:
            if stored_path.exists() and DOCUMENTS_DIR in stored_path.parents:
                stored_path.unlink()
        except OSError as exc:  # pragma: no cover
            logger.warning("stored file delete failed | doc_id=%s error=%s", document_id, type(exc).__name__)

        logger.info("document deleted | doc_id=%s chunks=%s", document_id, len(chunk_ids))
        return True

    def rebuild_all(self) -> list[IngestResult]:
        """임베딩 모델을 바꾼 경우 등 전체 재색인."""
        self.store.reset()
        results = []
        for row in self.documents():
            results.append(self.reindex_document(int(row["id"])))
        return results

    def chunk_rows(self, chunk_ids: Sequence[int]) -> dict:
        with db.connect() as conn:
            return db.get_chunks_by_ids(conn, chunk_ids)

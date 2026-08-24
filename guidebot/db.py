"""SQLite 기반 Metadata 저장소.

별도의 DB 서버를 두지 않고 data/database/guidebot.sqlite3 파일 하나만 사용한다.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Sequence

from .config import DB_PATH, LEGACY_DB_PATH, ensure_dirs

STATUS_ACTIVE = "active"          # 최신 버전, 기본 검색 대상
STATUS_SUPERSEDED = "superseded"  # 상위 버전이 등록되어 밀려난 문서
STATUS_DISABLED = "disabled"      # 사용자가 직접 비활성화한 문서

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_key       TEXT NOT NULL,
    title         TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    version       TEXT NOT NULL DEFAULT '1.0',
    ext           TEXT NOT NULL,
    file_hash     TEXT NOT NULL UNIQUE,
    source_path   TEXT NOT NULL,
    stored_path   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    page_count    INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    page_start   INTEGER NOT NULL DEFAULT 0,
    page_end     INTEGER NOT NULL DEFAULT 0,
    section      TEXT NOT NULL DEFAULT '',
    heading_path TEXT NOT NULL DEFAULT '',
    text         TEXT NOT NULL,
    char_len     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_key    ON documents(doc_key);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Document:
    id: int
    doc_key: str
    title: str
    file_name: str
    version: str
    ext: str
    file_hash: str
    source_path: str
    stored_path: str
    status: str
    chunk_count: int
    page_count: int
    registered_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Document":
        return cls(**{k: row[k] for k in row.keys() if k in cls.__annotations__})


@dataclass
class Chunk:
    id: int
    document_id: int
    chunk_index: int
    page_start: int
    page_end: int
    section: str
    heading_path: str
    text: str
    char_len: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Chunk":
        return cls(**{k: row[k] for k in row.keys() if k in cls.__annotations__})


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    """SQLite 접근을 감싸는 얇은 래퍼."""

    def __init__(self, path: Path | str | None = None) -> None:
        ensure_dirs()
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._adopt_legacy_database()
        self._init_schema()

    def _adopt_legacy_database(self) -> None:
        """이전 이름(sopbot.sqlite3)으로 저장된 DB가 있으면 이어서 사용한다.

        프로그램 이름이 GuideBot으로 바뀌어도 이미 등록해 둔 문서가 사라지지 않도록 한다.
        """
        if self.path != DB_PATH or self.path.exists():
            return
        if LEGACY_DB_PATH.exists():
            LEGACY_DB_PATH.rename(self.path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    def insert_document(
        self,
        *,
        doc_key: str,
        title: str,
        file_name: str,
        version: str,
        ext: str,
        file_hash: str,
        source_path: str,
        stored_path: str,
        page_count: int = 0,
        status: str = STATUS_ACTIVE,
    ) -> int:
        stamp = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO documents
                   (doc_key, title, file_name, version, ext, file_hash, source_path,
                    stored_path, status, chunk_count, page_count, registered_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,0,?,?,?)""",
                (
                    doc_key, title, file_name, version, ext, file_hash, source_path,
                    stored_path, status, page_count, stamp, stamp,
                ),
            )
            return int(cur.lastrowid)

    def get_document(self, document_id: int) -> Document | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return Document.from_row(row) if row else None

    def get_document_by_hash(self, file_hash: str) -> Document | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE file_hash = ?", (file_hash,)
            ).fetchone()
        return Document.from_row(row) if row else None

    def list_documents(self, statuses: Sequence[str] | None = None) -> list[Document]:
        query = "SELECT * FROM documents"
        params: list[str] = []
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            query += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY doc_key, version DESC, id DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Document.from_row(r) for r in rows]

    def documents_by_key(self, doc_key: str) -> list[Document]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE doc_key = ? ORDER BY id", (doc_key,)
            ).fetchall()
        return [Document.from_row(r) for r in rows]

    def set_status(self, document_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE documents SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_iso(), document_id),
            )

    def update_chunk_count(self, document_id: int, count: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE documents SET chunk_count = ?, updated_at = ? WHERE id = ?",
                (count, now_iso(), document_id),
            )

    def delete_document(self, document_id: int) -> None:
        """문서와 chunk를 함께 삭제한다(Vector Index 삭제는 ingest 단계에서 처리)."""
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    # ------------------------------------------------------------------
    # chunks
    # ------------------------------------------------------------------
    def replace_chunks(self, document_id: int, chunks: Sequence[dict]) -> list[int]:
        """문서의 chunk를 모두 교체하고 새 chunk id 목록을 반환한다."""
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            ids: list[int] = []
            for chunk in chunks:
                cur = conn.execute(
                    """INSERT INTO chunks
                       (document_id, chunk_index, page_start, page_end, section,
                        heading_path, text, char_len)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        document_id,
                        chunk["chunk_index"],
                        chunk.get("page_start", 0),
                        chunk.get("page_end", 0),
                        chunk.get("section", ""),
                        chunk.get("heading_path", ""),
                        chunk["text"],
                        len(chunk["text"]),
                    ),
                )
                ids.append(int(cur.lastrowid))
            conn.execute(
                "UPDATE documents SET chunk_count = ?, updated_at = ? WHERE id = ?",
                (len(ids), now_iso(), document_id),
            )
            return ids

    def chunk_ids_for_document(self, document_id: int) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM chunks WHERE document_id = ? ORDER BY chunk_index", (document_id,)
            ).fetchall()
        return [int(r["id"]) for r in rows]

    def get_chunks(self, chunk_ids: Sequence[int]) -> dict[int, Chunk]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" for _ in chunk_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM chunks WHERE id IN ({placeholders})", list(chunk_ids)
            ).fetchall()
        return {int(r["id"]): Chunk.from_row(r) for r in rows}

    def iter_chunks_for_search(
        self, statuses: Sequence[str] = (STATUS_ACTIVE,)
    ) -> list[tuple[Chunk, Document]]:
        """검색 대상 chunk와 소속 문서를 함께 읽는다."""
        placeholders = ",".join("?" for _ in statuses)
        with self.connect() as conn:
            rows = conn.execute(
                f"""SELECT c.*, d.id AS d_id, d.doc_key, d.title, d.file_name, d.version,
                           d.ext, d.file_hash, d.source_path, d.stored_path, d.status,
                           d.chunk_count, d.page_count, d.registered_at, d.updated_at
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE d.status IN ({placeholders})
                    ORDER BY c.id""",
                list(statuses),
            ).fetchall()

        result: list[tuple[Chunk, Document]] = []
        for row in rows:
            chunk = Chunk(
                id=int(row["id"]),
                document_id=int(row["document_id"]),
                chunk_index=int(row["chunk_index"]),
                page_start=int(row["page_start"]),
                page_end=int(row["page_end"]),
                section=row["section"],
                heading_path=row["heading_path"],
                text=row["text"],
                char_len=int(row["char_len"]),
            )
            document = Document(
                id=int(row["d_id"]),
                doc_key=row["doc_key"],
                title=row["title"],
                file_name=row["file_name"],
                version=row["version"],
                ext=row["ext"],
                file_hash=row["file_hash"],
                source_path=row["source_path"],
                stored_path=row["stored_path"],
                status=row["status"],
                chunk_count=int(row["chunk_count"]),
                page_count=int(row["page_count"]),
                registered_at=row["registered_at"],
                updated_at=row["updated_at"],
            )
            result.append((chunk, document))
        return result

    def documents_for_chunks(self, chunk_ids: Sequence[int]) -> dict[int, Document]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" for _ in chunk_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"""SELECT c.id AS chunk_id, d.* FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.id IN ({placeholders})""",
                list(chunk_ids),
            ).fetchall()
        return {int(r["chunk_id"]): Document.from_row(r) for r in rows}

    # ------------------------------------------------------------------
    # meta
    # ------------------------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def stats(self) -> dict[str, int]:
        with self.connect() as conn:
            docs = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
            active = conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE status = ?", (STATUS_ACTIVE,)
            ).fetchone()["n"]
            chunks = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
        return {"documents": int(docs), "active_documents": int(active), "chunks": int(chunks)}

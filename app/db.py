"""SQLite 메타데이터 저장소 (요구사항 4 - Metadata 저장).

별도 DB 서버 없이 단일 파일(sqlite3)만 사용한다.
chunks.id 가 Vector Index의 ID로 그대로 사용된다.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from app.config import DB_PATH, ensure_directories

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_key      TEXT    NOT NULL,
    title        TEXT    NOT NULL,
    filename     TEXT    NOT NULL,
    version      TEXT    NOT NULL DEFAULT '',
    version_key  TEXT    NOT NULL DEFAULT '',
    ext          TEXT    NOT NULL DEFAULT '',
    sha256       TEXT    NOT NULL,
    stored_path  TEXT    NOT NULL,
    source_path  TEXT    NOT NULL DEFAULT '',
    page_count   INTEGER NOT NULL DEFAULT 0,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    status       TEXT    NOT NULL DEFAULT 'active',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    page         INTEGER,
    section      TEXT    NOT NULL DEFAULT '',
    heading_path TEXT    NOT NULL DEFAULT '',
    text         TEXT    NOT NULL,
    char_count   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_key   ON documents(doc_key);
CREATE INDEX IF NOT EXISTS idx_documents_sha   ON documents(sha256);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """트랜잭션 단위 커넥션. 예외 발생 시 자동 rollback."""
    ensure_directories()
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """최초 실행 시 스키마를 생성한다."""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------- documents
def insert_document(
    conn: sqlite3.Connection,
    *,
    doc_key: str,
    title: str,
    filename: str,
    version: str,
    version_key: str,
    ext: str,
    sha256: str,
    stored_path: str,
    source_path: str,
    page_count: int,
    status: str = "active",
) -> int:
    timestamp = now()
    cursor = conn.execute(
        """
        INSERT INTO documents (doc_key, title, filename, version, version_key, ext,
                               sha256, stored_path, source_path, page_count,
                               chunk_count, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            doc_key, title, filename, version, version_key, ext, sha256,
            stored_path, source_path, page_count, status, timestamp, timestamp,
        ),
    )
    return int(cursor.lastrowid)


def update_document(conn: sqlite3.Connection, document_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE documents SET {assignments} WHERE id = ?",
        (*fields.values(), document_id),
    )


def get_document(conn: sqlite3.Connection, document_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()


def get_document_by_sha(conn: sqlite3.Connection, sha256: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM documents WHERE sha256 = ? LIMIT 1", (sha256,)
    ).fetchone()


def list_documents(
    conn: sqlite3.Connection, *, only_active: bool = False
) -> list[sqlite3.Row]:
    query = "SELECT * FROM documents"
    if only_active:
        query += " WHERE status = 'active'"
    query += " ORDER BY doc_key ASC, version_key DESC, id DESC"
    return list(conn.execute(query).fetchall())


def list_versions(conn: sqlite3.Connection, doc_key: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM documents WHERE doc_key = ? ORDER BY version_key DESC, id DESC",
            (doc_key,),
        ).fetchall()
    )


def delete_document_row(conn: sqlite3.Connection, document_id: int) -> None:
    """documents + (FK CASCADE) chunks 삭제."""
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


# ------------------------------------------------------------------- chunks
def insert_chunks(
    conn: sqlite3.Connection, document_id: int, chunks: Sequence[dict]
) -> list[int]:
    """청크를 저장하고 생성된 id 목록을 반환한다(= vector id)."""
    timestamp = now()
    ids: list[int] = []
    for chunk in chunks:
        cursor = conn.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, page, section,
                                heading_path, text, char_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                chunk["chunk_index"],
                chunk.get("page"),
                chunk.get("section", ""),
                chunk.get("heading_path", ""),
                chunk["text"],
                len(chunk["text"]),
                timestamp,
            ),
        )
        ids.append(int(cursor.lastrowid))
    conn.execute(
        "UPDATE documents SET chunk_count = ?, updated_at = ? WHERE id = ?",
        (len(chunks), timestamp, document_id),
    )
    return ids


def get_chunk_ids(conn: sqlite3.Connection, document_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
    ).fetchall()
    return [int(row["id"]) for row in rows]


def delete_chunks(conn: sqlite3.Connection, document_id: int) -> list[int]:
    ids = get_chunk_ids(conn, document_id)
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    conn.execute(
        "UPDATE documents SET chunk_count = 0, updated_at = ? WHERE id = ?",
        (now(), document_id),
    )
    return ids


def get_chunks_by_ids(
    conn: sqlite3.Connection, chunk_ids: Iterable[int]
) -> dict[int, sqlite3.Row]:
    ids = [int(i) for i in chunk_ids]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT c.*, d.title, d.version, d.filename, d.stored_path, d.status,
               d.doc_key, d.id AS doc_id
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.id IN ({placeholders})
        """,
        ids,
    ).fetchall()
    return {int(row["id"]): row for row in rows}


def iter_active_chunks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """키워드 인덱스(BM25) 구축용 - 활성 문서의 청크만 반환."""
    return list(
        conn.execute(
            """
            SELECT c.id, c.text, c.section, c.heading_path, d.title, d.version
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE d.status = 'active'
            """
        ).fetchall()
    )


# --------------------------------------------------------------------- meta
def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def stats(conn: sqlite3.Connection) -> dict:
    documents = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status = 'active'"
    ).fetchone()["c"]
    chunks = conn.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"]
    return {"documents": documents, "active_documents": active, "chunks": chunks}

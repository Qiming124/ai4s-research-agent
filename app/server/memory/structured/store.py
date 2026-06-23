# L4 结构化科研记忆：定理、假设、实验结论与引用关系（SQLite）。

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from server.config import get_settings

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS structured_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    kind        TEXT NOT NULL CHECK(kind IN ('theorem','hypothesis','conclusion','citation','note')),
    title       TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_structured_session ON structured_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_structured_kind ON structured_memory(kind);
"""


class StructuredMemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def create_entry(
        self,
        *,
        session_id: str | None,
        kind: str,
        title: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO structured_memory (session_id, kind, title, body, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, kind, title, body, meta_json),
            )
            row_id = cursor.lastrowid
            row = self._conn.execute(
                "SELECT * FROM structured_memory WHERE id = ?",
                (row_id,),
            ).fetchone()
            self._conn.commit()
        return self._row_to_dict(row)

    def list_entries(
        self,
        *,
        session_id: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM structured_memory {where} "
            "ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        metadata_raw = row["metadata"] or "{}"
        try:
            metadata = json.loads(metadata_raw)
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "kind": row["kind"],
            "title": row["title"],
            "body": row["body"],
            "metadata": metadata if isinstance(metadata, dict) else {},
            "created_at": row["created_at"],
        }


_store: StructuredMemoryStore | None = None


def get_structured_memory_store() -> StructuredMemoryStore:
    global _store
    if _store is None:
        settings = get_settings()
        _store = StructuredMemoryStore(settings.session_db_path)
    return _store

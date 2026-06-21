# 会话级 RAG 引用：仅存 doc_id + snippet 预览，不写入 L2 消息正文。

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS session_rag_refs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    doc_id      TEXT    NOT NULL,
    snippet     TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_session_rag_refs_session
    ON session_rag_refs(session_id);
"""


class SessionRagRefStore:
    """在 sessions.db 中记录会话检索到的文档引用。"""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def add_ref(self, session_id: str, doc_id: str, snippet: str) -> None:
        preview = snippet[:240] if snippet else ""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO session_rag_refs (session_id, doc_id, snippet)
                VALUES (?, ?, ?)
                """,
                (session_id, doc_id, preview),
            )
            self._conn.commit()

    def get_refs(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT doc_id, snippet, created_at
                FROM session_rag_refs
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                "doc_id": row["doc_id"],
                "snippet": row["snippet"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM session_rag_refs WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()

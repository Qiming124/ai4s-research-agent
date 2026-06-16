# =============================================================================
# SQLite 会话持久化存储。
#
# 职责：将会话 ID 与消息列表持久化到 SQLite 文件，进程重启后数据不丢失。
#
# 架构位置：
#     get_session_store() → SESSION_STORE_BACKEND=sqlite 时返回本类实例
#
# 线程安全：所有 DB 操作在 threading.Lock 内执行（单 worker 场景）。
# 多 worker 部署需换 Redis 后端（Phase 2A 后续）。
#
# Debug：
#     - 重启后会话丢失 → 检查 SESSION_STORE_BACKEND 是否为 sqlite
#     - database is locked → 多 worker 并发写 SQLite，需改单 worker 或换 Redis
# =============================================================================

from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path

from server.memory.base import BaseSessionStore
from shared.schemas import ChatMessage

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL CHECK(role IN ('system','user','assistant')),
    content     TEXT    NOT NULL,
    seq         INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE(session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
"""


class SQLiteSessionStore(BaseSessionStore):
    # 基于 SQLite 文件的会话仓库，支持进程重启后恢复历史。

    def __init__(self, db_path: str | Path) -> None:
        # 参数 db_path — SQLite 数据库文件路径；父目录不存在时自动创建。
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        # 建表（幂等）；启动时自动执行。
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()
            self._migrate()

    def _migrate(self) -> None:
        # Phase 2A：为已有数据库追加 reasoning_content 列。
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "reasoning_content" not in cols:
            self._conn.execute(
                "ALTER TABLE messages ADD COLUMN reasoning_content TEXT"
            )
            self._conn.commit()

    def create_session_id(self) -> str:
        return str(uuid.uuid4())

    def get_or_create(self, session_id: str | None) -> str:
        if not session_id:
            session_id = self.create_session_id()
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
                (session_id,),
            )
            self._conn.commit()
        return session_id

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT role, content, reasoning_content FROM messages
                WHERE session_id = ?
                ORDER BY seq
                """,
                (session_id,),
            ).fetchall()
        return [
            ChatMessage(
                role=row["role"],
                content=row["content"],
                reasoning_content=row["reasoning_content"],
            )
            for row in rows
        ]

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
                (session_id,),
            )
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), -1) AS max_seq FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            next_seq = int(row["max_seq"]) + 1
            self._conn.execute(
                """
                INSERT INTO messages (session_id, role, content, seq, reasoning_content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    message.role,
                    message.content,
                    next_seq,
                    message.reasoning_content,
                ),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at = datetime('now') WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not exists:
                return False
            self._conn.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()
        return True

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def session_exists(self, session_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row is not None

    def list_session_ids(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT session_id FROM sessions ORDER BY updated_at",
            ).fetchall()
        return [row["session_id"] for row in rows]

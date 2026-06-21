"""Token usage event store and aggregation (SQLite, same DB as sessions)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from server.config import get_settings

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS token_usage_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT    NOT NULL,
    agent_name          TEXT    NOT NULL DEFAULT 'general',
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens        INTEGER NOT NULL DEFAULT 0,
    usage_day           TEXT    NOT NULL DEFAULT (date('now')),
    recorded_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage_events(session_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent_day ON token_usage_events(agent_name, usage_day);
"""


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class TokenUsageStore:
    """Persist per-request token usage and expose aggregates."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def record(
        self,
        session_id: str,
        agent_name: str,
        usage: dict[str, Any] | None,
    ) -> None:
        if not usage:
            return
        prompt = _parse_int(usage.get("prompt_tokens"))
        completion = _parse_int(usage.get("completion_tokens"))
        total = _parse_int(usage.get("total_tokens"), prompt + completion)
        if total <= 0 and prompt <= 0 and completion <= 0:
            return
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO token_usage_events
                    (session_id, agent_name, prompt_tokens, completion_tokens, total_tokens)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, agent_name or "general", prompt, completion, total),
            )
            self._conn.commit()

    def query(
        self,
        *,
        session_id: str | None = None,
        agent_name: str | None = None,
        day: str | None = None,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if agent_name:
            clauses.append("agent_name = ?")
            params.append(agent_name)
        if day:
            clauses.append("usage_day = ?")
            params.append(day)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT
                COUNT(*) AS event_count,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM token_usage_events
            {where}
        """
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()

        by_agent_sql = f"""
            SELECT agent_name,
                   COUNT(*) AS event_count,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM token_usage_events
            {where}
            GROUP BY agent_name
            ORDER BY total_tokens DESC
        """
        with self._lock:
            agent_rows = self._conn.execute(by_agent_sql, params).fetchall()

        return {
            "filters": {
                "session_id": session_id,
                "agent_name": agent_name,
                "day": day,
            },
            "totals": {
                "event_count": int(row["event_count"]),
                "prompt_tokens": int(row["prompt_tokens"]),
                "completion_tokens": int(row["completion_tokens"]),
                "total_tokens": int(row["total_tokens"]),
            },
            "by_agent": [
                {
                    "agent_name": r["agent_name"],
                    "event_count": int(r["event_count"]),
                    "total_tokens": int(r["total_tokens"]),
                }
                for r in agent_rows
            ],
        }


_token_store: TokenUsageStore | None = None


def get_token_usage_store() -> TokenUsageStore:
    global _token_store
    if _token_store is None:
        settings = get_settings()
        db_path = settings.session_db_path
        if settings.session_store_backend != "sqlite":
            db_path = "./data/token_usage.db"
        _token_store = TokenUsageStore(db_path)
    return _token_store


def reset_token_usage_store() -> None:
    global _token_store
    _token_store = None


def record_token_usage(
    session_id: str,
    agent_name: str,
    usage: dict[str, Any] | None,
) -> None:
    settings = get_settings()
    if not settings.enable_token_stats:
        return
    get_token_usage_store().record(session_id, agent_name, usage)

"""Token 用量持久化：写入 SQLite 事件表 + 聚合查询 API。

职责：
    - record():    每条 chat turn 结束后写入 token 用量事件
    - query():     按 session_id / agent_name / day 聚合查询
    - maintain():  auto-create table + indexes on first use

存储位置：
    - SESSION_STORE_BACKEND=sqlite → 写入 sessions.db（同数据库，不同表）
    - SESSION_STORE_BACKEND=memory → 写入 data/token_usage.db

表结构：
    token_usage_events(
        id, session_id, agent_name,
        prompt_tokens, completion_tokens, total_tokens,
        usage_day, recorded_at
    )
    索引：session_id 索引 + (agent_name, usage_day) 复合索引

API 端点：
    GET /v1/stats/tokens?session_id=xxx&agent_name=yyy&day=2025-01-01
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from server.config import get_settings
from shared.paths import DATA_ROOT

# ── 建表 DDL（幂等） ─────────────────────────────────────────
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
    """安全地将任意值转为整数，失败时返回默认值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class TokenUsageStore:
    """
    Token 用量持久化存储。

    方法：
        record(session_id, agent_name, usage_dict)  — 写入一条事件
        query(session_id?, agent_name?, day?)        — 聚合查询

    线程安全：所有 DB 操作在 threading.Lock 内执行。
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        初始化存储。

        参数:
            db_path: SQLite 数据库文件路径；父目录自动创建
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # check_same_thread=False 允许跨线程复用连接
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
        """
        写入一次 token 用量事件。

        参数:
            session_id: 会话 ID
            agent_name: Agent 名（general/theory/experiment/literature）
            usage: DeepSeek API 返回的 usage 字典（含 prompt_tokens / completion_tokens / total_tokens）

        策略：
            - usage 为 None → 直接返回
            - total_tokens 缺失 → 用 prompt+completion 推算
            - 三项皆 0 → 不写入（避免空条目污染聚合）
        """
        if not usage:
            return
        prompt = _parse_int(usage.get("prompt_tokens"))
        completion = _parse_int(usage.get("completion_tokens"))
        total = _parse_int(usage.get("total_tokens"), prompt + completion)
        if total <= 0 and prompt <= 0 and completion <= 0:
            return  # 无有效用量数据
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
        """
        聚合查询 token 用量。

        参数:
            session_id: 可选按会话 ID 过滤
            agent_name: 可选按 Agent 名过滤
            day: 可选按日期过滤（YYYY-MM-DD）

        返回:
            {
                "filters": {...},
                "totals": {"event_count": N, "prompt_tokens": X, "completion_tokens": Y, "total_tokens": Z},
                "by_agent": [{"agent_name": ..., "event_count": N, "total_tokens": Z}, ...]
            }
        """
        # 构建 WHERE 子句（参数化查询防止 SQL 注入）
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

        # ── 汇总查询（单次聚合） ──
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

        # ── 按 Agent 分组查询 ──
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


# ── 模块级单例 ──────────────────────────────────────────────

_token_store: TokenUsageStore | None = None


def get_token_usage_store() -> TokenUsageStore:
    """
    获取全局 TokenUsageStore 单例。

    数据库路径根据 SESSION_STORE_BACKEND 选择：
        sqlite → sessions.db（与会话共用数据库）
        memory → data/token_usage.db（独立数据库文件）
    """
    global _token_store
    if _token_store is None:
        settings = get_settings()
        db_path = settings.session_db_path
        if settings.session_store_backend != "sqlite":
            db_path = str(DATA_ROOT / "token_usage.db")
        _token_store = TokenUsageStore(db_path)
    return _token_store


def reset_token_usage_store() -> None:
    """清除全局单例（供测试使用）。"""
    global _token_store
    _token_store = None


def record_token_usage(
    session_id: str,
    agent_name: str,
    usage: dict[str, Any] | None,
) -> None:
    """
    便捷函数：检查 ENABLE_TOKEN_STATS 后写入用量。

    由 finalize_chat_turn() 在每个 chat turn 结束后调用。
    """
    settings = get_settings()
    if not settings.enable_token_stats:
        return
    get_token_usage_store().record(session_id, agent_name, usage)

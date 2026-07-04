# 验证账本：记录每次 SymPy / 数值 / 实验验证结果。

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import get_settings

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS verification_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL DEFAULT 'default',
    session_id  TEXT,
    entry_id    INTEGER,
    claim_id    TEXT NOT NULL DEFAULT '',
    tier        TEXT NOT NULL CHECK(tier IN ('symbolic','numerical','experiment')),
    executor    TEXT NOT NULL DEFAULT '',
    agent_name  TEXT NOT NULL DEFAULT '',
    passed      INTEGER NOT NULL DEFAULT 0,
    result      TEXT NOT NULL DEFAULT '{}',
    artifacts   TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_vl_project ON verification_ledger(project_id);
CREATE INDEX IF NOT EXISTS idx_vl_entry ON verification_ledger(entry_id);
CREATE INDEX IF NOT EXISTS idx_vl_session ON verification_ledger(session_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VerificationLedgerStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def append(
        self,
        *,
        project_id: str = "default",
        session_id: str | None,
        entry_id: int | None,
        claim_id: str,
        tier: str,
        executor: str,
        agent_name: str,
        passed: bool,
        result: dict[str, Any],
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO verification_ledger
                (project_id, session_id, entry_id, claim_id, tier, executor,
                 agent_name, passed, result, artifacts, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    session_id,
                    entry_id,
                    claim_id,
                    tier,
                    executor,
                    agent_name,
                    1 if passed else 0,
                    json.dumps(result, ensure_ascii=False),
                    json.dumps(artifacts or [], ensure_ascii=False),
                    _now_iso(),
                ),
            )
            row_id = cursor.lastrowid
            row = self._conn.execute(
                "SELECT * FROM verification_ledger WHERE id = ?", (row_id,)
            ).fetchone()
            self._conn.commit()
        return self._row_to_dict(row)

    def list_records(
        self,
        *,
        project_id: str | None = None,
        session_id: str | None = None,
        entry_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if entry_id is not None:
            clauses.append("entry_id = ?")
            params.append(entry_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM verification_ledger {where} "
            "ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def compute_entry_status(self, entry_id: int) -> str:
        """根据验证账本推断定理状态。"""
        records = self.list_records(entry_id=entry_id, limit=50)
        if not records:
            return "draft"
        tiers = {r["tier"]: r["passed"] for r in records}
        if tiers.get("experiment"):
            return "experiment_verified" if tiers["experiment"] else "experiment_failed"
        if tiers.get("numerical"):
            return "numerically_verified" if tiers["numerical"] else "numerical_failed"
        if tiers.get("symbolic"):
            return "symbolically_verified" if tiers["symbolic"] else "symbolic_failed"
        return "draft"

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "session_id": row["session_id"],
            "entry_id": row["entry_id"],
            "claim_id": row["claim_id"],
            "tier": row["tier"],
            "executor": row["executor"],
            "agent_name": row["agent_name"],
            "passed": bool(row["passed"]),
            "result": json.loads(row["result"] or "{}"),
            "artifacts": json.loads(row["artifacts"] or "[]"),
            "created_at": row["created_at"],
        }


_ledger_store: VerificationLedgerStore | None = None


def get_verification_ledger() -> VerificationLedgerStore:
    global _ledger_store
    if _ledger_store is None:
        settings = get_settings()
        _ledger_store = VerificationLedgerStore(settings.session_db_path)
    return _ledger_store

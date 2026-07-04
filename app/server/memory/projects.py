# 课题（Project）存储：实验室小组研究单元。

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import get_settings
from shared.paths import DATA_ROOT

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    created_by      TEXT NOT NULL DEFAULT '',
    default_assumptions TEXT NOT NULL DEFAULT '[]',
    workspace_path  TEXT NOT NULL DEFAULT '',
    rag_namespace   TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL CHECK(role IN ('pi','theorist','experimenter','reviewer','literature')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS project_tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    assignee_role TEXT NOT NULL DEFAULT 'theorist',
    status      TEXT NOT NULL DEFAULT 'todo'
                CHECK(status IN ('todo','in_progress','blocked','done')),
    related_entry_id INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS project_sessions (
    project_id  TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    PRIMARY KEY (project_id, session_id)
);

CREATE TABLE IF NOT EXISTS sync_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    action      TEXT NOT NULL,
    actor       TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memory_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL,
    version     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'draft',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()
        self._ensure_default_project()
        self._ensure_default_tasks()

    def _ensure_default_project(self) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM projects WHERE id = 'default'"
            ).fetchone()
            if row:
                return
            root = DATA_ROOT / "projects" / "default"
            (root / "theory").mkdir(parents=True, exist_ok=True)
            (root / "experiments" / "logs").mkdir(parents=True, exist_ok=True)
            self._conn.execute(
                """
                INSERT INTO projects (id, name, description, workspace_path, rag_namespace)
                VALUES ('default', '默认课题', '损失函数局部极小值理论研究', ?, 'default')
                """,
                (str(root / "theory"),),
            )
            for role in ("pi", "theorist", "experimenter", "reviewer", "literature"):
                self._conn.execute(
                    "INSERT INTO project_members (project_id, user_id, role) VALUES ('default', ?, ?)",
                    (f"member-{role}", role),
                )
            self._conn.commit()

    def _ensure_default_tasks(self) -> None:
        """为默认课题预置示例任务（仅当尚无任务时）。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM project_tasks WHERE project_id = 'default'"
            ).fetchone()
            if row and int(row["c"]) > 0:
                return
            seeds = (
                ("文献调研：局部极小值综述", "literature", "todo"),
                ("形式化：PL 条件推导", "theorist", "todo"),
                ("数值验证：二次损失临界点", "experimenter", "todo"),
            )
            now = _now_iso()
            for title, role, status in seeds:
                self._conn.execute(
                    """
                    INSERT INTO project_tasks
                    (project_id, title, description, assignee_role, status, created_at, updated_at)
                    VALUES ('default', ?, '', ?, ?, ?, ?)
                    """,
                    (title, role, status, now, now),
                )
            self._conn.commit()

    def resolve_project_id(self, project_id: str) -> str | None:
        """解析课题 ID；不存在时若可回退则返回 default。"""
        pid = (project_id or "").strip() or "default"
        if self.get_project(pid):
            return pid
        if pid != "default" and self.get_project("default"):
            return "default"
        return None

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY created_at ASC"
            ).fetchall()
        return [self._project_row(r) for r in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._project_row(row) if row else None

    def create_project(
        self,
        name: str,
        description: str = "",
        created_by: str = "",
    ) -> dict[str, Any]:
        pid = str(uuid.uuid4())[:12]
        root = DATA_ROOT / "projects" / pid
        (root / "theory").mkdir(parents=True, exist_ok=True)
        (root / "experiments" / "logs").mkdir(parents=True, exist_ok=True)
        now = _now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO projects
                (id, name, description, created_by, workspace_path, rag_namespace, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, name, description, created_by, str(root / "theory"), pid, now, now),
            )
            self._conn.execute(
                "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'pi')",
                (pid, created_by or "owner"),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (pid,)
            ).fetchone()
        return self._project_row(row)

    def list_members(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM project_members WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "user_id": r["user_id"],
                "role": r["role"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def list_tasks(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM project_tasks WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        assignee_role: str = "theorist",
        related_entry_id: int | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO project_tasks
                (project_id, title, description, assignee_role, related_entry_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, title, description, assignee_role, related_entry_id, now, now),
            )
            row = self._conn.execute(
                "SELECT * FROM project_tasks WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            self._conn.commit()
        return dict(row)

    def update_task_status(self, task_id: int, status: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._lock:
            self._conn.execute(
                "UPDATE project_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )
            row = self._conn.execute(
                "SELECT * FROM project_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            self._conn.commit()
        return dict(row) if row else None

    def link_session(self, project_id: str, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO project_sessions (project_id, session_id) VALUES (?, ?)",
                (project_id, session_id),
            )
            self._conn.commit()

    def list_sessions(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT session_id, project_id
                FROM project_sessions
                WHERE project_id = ?
                ORDER BY rowid DESC
                """,
                (project_id,),
            ).fetchall()
        return [{"session_id": r["session_id"], "project_id": r["project_id"]} for r in rows]

    def get_project_for_session(self, session_id: str) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT project_id FROM project_sessions WHERE session_id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
        return row["project_id"] if row else "default"

    def append_audit(
        self,
        project_id: str,
        action: str,
        actor: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO sync_audit_log (project_id, action, actor, payload) VALUES (?, ?, ?, ?)",
                (project_id, action, actor, json.dumps(payload or {}, ensure_ascii=False)),
            )
            self._conn.commit()

    def list_audit(self, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sync_audit_log WHERE project_id = ? ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "action": r["action"],
                "actor": r["actor"],
                "payload": json.loads(r["payload"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def save_entry_version(
        self,
        entry_id: int,
        title: str,
        body: str,
        metadata: dict[str, Any],
        status: str = "draft",
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM memory_versions WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            version = int(row["v"]) + 1
            cursor = self._conn.execute(
                """
                INSERT INTO memory_versions (entry_id, version, title, body, metadata, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    version,
                    title,
                    body,
                    json.dumps(metadata, ensure_ascii=False),
                    status,
                ),
            )
            saved = self._conn.execute(
                "SELECT * FROM memory_versions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            self._conn.commit()
        out = dict(saved)
        out["metadata"] = json.loads(out["metadata"] or "{}")
        return out

    def list_entry_versions(self, entry_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM memory_versions WHERE entry_id = ? ORDER BY version DESC",
                (entry_id,),
            ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["metadata"] = json.loads(item["metadata"] or "{}")
            result.append(item)
        return result

    @staticmethod
    def _project_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "created_by": row["created_by"],
            "default_assumptions": json.loads(row["default_assumptions"] or "[]"),
            "workspace_path": row["workspace_path"],
            "rag_namespace": row["rag_namespace"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


_project_store: ProjectStore | None = None


def get_project_store() -> ProjectStore:
    global _project_store
    if _project_store is None:
        settings = get_settings()
        _project_store = ProjectStore(settings.session_db_path)
    return _project_store

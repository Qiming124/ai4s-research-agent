# =============================================================================
# 课题（Project）存储：实验室小组研究单元。
#
# 职责：
#     1. SQLite 持久化课题元数据、成员、任务与会话绑定
#     2. 管理工作区路径、RAG namespace 与默认假设
#     3. delete_project() 删除课题行（级联由 API 层处理磁盘与会话）
#
# 架构位置：
#     - 被调用：server/api/projects.py、sync.py、theory.py
#     - 调用：server/config.py、shared/paths.DATA_ROOT
#
# 阅读提示：
#     - 新人先看 ProjectStore.create_project / resolve_project_id / delete_project
#
# Debug：
#     - default 不可删 → delete_project 显式拒绝
#     - 会话未绑定课题 → link_session 或 get_project_for_session
# =============================================================================

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

    def delete_project(self, project_id: str) -> dict[str, Any] | None:
        """
        删除课题行及其成员/任务/会话绑定/审计记录。

        不删会话消息与磁盘目录——由 API 层级联处理。
        默认课题 default 不可删。

        参数:
            project_id: 课题 ID 或别名

        返回:
            {"project_id", "session_ids", "workspace_root"}；不存在或 default 则 None
        """
        if project_id == "default":
            raise ValueError("默认课题不可删除")
        project = self.get_project(project_id)
        if not project:
            return None
        session_ids = [
            s["session_id"] for s in self.list_sessions(project_id, existing_only=False)
        ]
        workspace_root = str(DATA_ROOT / "projects" / project_id)
        with self._lock:
            self._conn.execute(
                "DELETE FROM project_members WHERE project_id = ?", (project_id,)
            )
            self._conn.execute(
                "DELETE FROM project_tasks WHERE project_id = ?", (project_id,)
            )
            self._conn.execute(
                "DELETE FROM project_sessions WHERE project_id = ?", (project_id,)
            )
            self._conn.execute(
                "DELETE FROM sync_audit_log WHERE project_id = ?", (project_id,)
            )
            self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.commit()
        return {
            "project_id": project_id,
            "session_ids": session_ids,
            "workspace_root": workspace_root,
            "name": project.get("name", ""),
        }

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        if name is not None and name.strip():
            updates["name"] = name.strip()
        if description is not None:
            updates["description"] = description
        if not updates:
            return self.get_project(project_id)
        updates["updated_at"] = _now_iso()
        cols = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [project_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE projects SET {cols} WHERE id = ?",
                values,
            )
            self._conn.commit()
        return self.get_project(project_id)

    def ensure_workspace(self, project_id: str) -> Path:
        """确保课题理论工作区目录存在，并返回路径。"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"课题不存在: {project_id}")
        root = Path(project["workspace_path"] or (DATA_ROOT / "projects" / project_id / "theory"))
        root.mkdir(parents=True, exist_ok=True)
        (root / "lemmas").mkdir(parents=True, exist_ok=True)
        (root / "proofs").mkdir(parents=True, exist_ok=True)
        return root

    def seed_theory_workspace(self, project_id: str) -> Path:
        """确保课题 theory 目录存在；不再复制 A1–A6 / symbols 等已下线种子模板。"""
        root = self.ensure_workspace(project_id)
        keep = root / ".gitkeep"
        if not keep.exists():
            keep.write_text(
                "# 理论工作区文件 HTTP 与 A1–A6 种子注入已下线；假设请写入 L4 定理库。\n",
                encoding="utf-8",
            )
        return root

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
        """将会话独家绑定到课题（先解除其它课题关联，避免串题）。"""
        with self._lock:
            self._conn.execute(
                "DELETE FROM project_sessions WHERE session_id = ?",
                (session_id,),
            )
            self._conn.execute(
                "INSERT INTO project_sessions (project_id, session_id) VALUES (?, ?)",
                (project_id, session_id),
            )
            self._conn.commit()

    def unlink_session(
        self,
        session_id: str,
        *,
        project_id: str | None = None,
    ) -> int:
        """解除会话与课题的关联；未指定 project_id 时解除该会话的全部课题绑定。"""
        with self._lock:
            if project_id:
                cur = self._conn.execute(
                    "DELETE FROM project_sessions WHERE project_id = ? AND session_id = ?",
                    (project_id, session_id),
                )
            else:
                cur = self._conn.execute(
                    "DELETE FROM project_sessions WHERE session_id = ?",
                    (session_id,),
                )
            self._conn.commit()
        return int(cur.rowcount or 0)

    def prune_orphan_session_links(self) -> int:
        """删除 sessions 表中已不存在的课题关联（幽灵链接）。"""
        with self._lock:
            cur = self._conn.execute(
                """
                DELETE FROM project_sessions
                WHERE session_id NOT IN (SELECT session_id FROM sessions)
                """
            )
            self._conn.commit()
        return int(cur.rowcount or 0)

    def list_sessions(
        self,
        project_id: str,
        *,
        existing_only: bool = True,
    ) -> list[dict[str, Any]]:
        """列出课题关联会话。

        existing_only=True（默认）：只返回 sessions 表中仍存在的会话，并顺带清理幽灵链接。
        """
        if existing_only:
            self.prune_orphan_session_links()
        with self._lock:
            if existing_only:
                rows = self._conn.execute(
                    """
                    SELECT ps.session_id, ps.project_id
                    FROM project_sessions ps
                    INNER JOIN sessions s ON s.session_id = ps.session_id
                    WHERE ps.project_id = ?
                    ORDER BY ps.rowid DESC
                    """,
                    (project_id,),
                ).fetchall()
            else:
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

# =============================================================================
# L4 结构化科研记忆：定理、假设、实验结论与引用关系。
#
# 职责：
#     1. SQLite 存储 structured_memory 表与 memory_edges 图谱边
#     2. CRUD 条目、按 session/kind 查询、图谱导出
#     3. get_structured_memory_store() 线程安全单例
#
# 架构位置：
#     - 被调用：server/api/structured_memory.py、export/builder.py、
#               memory/structured/extract.py、graph.py、dag.py、injection.py
#     - 调用：server/config.py
#
# 阅读提示：
#     - 新人先看 StructuredMemoryStore.create_entry / list_entries / add_edge
#
# Debug：
#     - kind CHECK 失败 → 仅允许 theorem/hypothesis/conclusion/citation/note
#     - 图谱为空 → memory_edges 未创建或 session 过滤
# =============================================================================

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

CREATE TABLE IF NOT EXISTS memory_edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id     INTEGER NOT NULL,
    to_id       INTEGER NOT NULL,
    relation    TEXT NOT NULL CHECK(relation IN ('depends_on','contradicts','supports','cites')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (from_id) REFERENCES structured_memory(id),
    FOREIGN KEY (to_id) REFERENCES structured_memory(id)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON memory_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON memory_edges(to_id);
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

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM structured_memory WHERE id = ?",
                (entry_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def update_entry(
        self,
        entry_id: int,
        *,
        kind: str | None = None,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        current = self.get_entry(entry_id)
        if not current:
            return None
        new_kind = kind if kind is not None else current["kind"]
        new_title = title if title is not None else current["title"]
        new_body = body if body is not None else current["body"]
        new_meta = metadata if metadata is not None else current["metadata"]
        meta_json = json.dumps(new_meta or {}, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """
                UPDATE structured_memory
                SET kind = ?, title = ?, body = ?, metadata = ?
                WHERE id = ?
                """,
                (new_kind, new_title, new_body, meta_json, entry_id),
            )
            row = self._conn.execute(
                "SELECT * FROM structured_memory WHERE id = ?",
                (entry_id,),
            ).fetchone()
            self._conn.commit()
        return self._row_to_dict(row) if row else None

    def delete_entry(self, entry_id: int) -> bool:
        with self._lock:
            self._conn.execute(
                "DELETE FROM memory_edges WHERE from_id = ? OR to_id = ?",
                (entry_id, entry_id),
            )
            cursor = self._conn.execute(
                "DELETE FROM structured_memory WHERE id = ?",
                (entry_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def list_entries(
        self,
        *,
        session_id: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        global_only: bool = False,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if global_only:
            clauses.append("session_id IS NULL")
        elif session_id is not None:
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

    def create_edge(
        self,
        *,
        from_id: int,
        to_id: int,
        relation: str = "depends_on",
    ) -> dict[str, Any]:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO memory_edges (from_id, to_id, relation)
                VALUES (?, ?, ?)
                """,
                (from_id, to_id, relation),
            )
            row_id = cursor.lastrowid
            row = self._conn.execute(
                "SELECT * FROM memory_edges WHERE id = ?",
                (row_id,),
            ).fetchone()
            self._conn.commit()
        return {
            "id": row["id"],
            "from_id": row["from_id"],
            "to_id": row["to_id"],
            "relation": row["relation"],
            "created_at": row["created_at"],
        }

    def list_edges(self, *, session_id: str | None = None) -> list[dict[str, Any]]:
        """列出与会话相关的边（端点属于该会话或全局）。"""
        with self._lock:
            if session_id:
                rows = self._conn.execute(
                    """
                    SELECT e.* FROM memory_edges e
                    JOIN structured_memory m1 ON e.from_id = m1.id
                    JOIN structured_memory m2 ON e.to_id = m2.id
                    WHERE m1.session_id = ? OR m2.session_id = ?
                       OR m1.session_id IS NULL OR m2.session_id IS NULL
                    ORDER BY e.created_at DESC
                    """,
                    (session_id, session_id),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM memory_edges ORDER BY created_at DESC"
                ).fetchall()
        return [
            {
                "id": r["id"],
                "from_id": r["from_id"],
                "to_id": r["to_id"],
                "relation": r["relation"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_graph(self, *, session_id: str | None = None) -> dict[str, Any]:
        """返回节点 + 边（知识图谱）。

        刷新时按 metadata / 正文中的依据引用补建缺失的 depends_on 边，
        使「关系图谱」在仅有正文引用时也能显示依赖。
        """
        nodes = self.list_entries(session_id=session_id, limit=200)
        global_nodes = self.list_entries(global_only=True, limit=100)
        seen_ids = {n["id"] for n in nodes}
        for gn in global_nodes:
            if gn["id"] not in seen_ids:
                nodes.append(gn)
                seen_ids.add(gn["id"])

        from server.memory.structured.graph import (
            extract_metadata_from_body,
            link_depends_on_from_metadata,
        )

        for node in list(nodes):
            meta = dict(node.get("metadata") or {})
            if not meta.get("depends_on_refs") and node.get("body"):
                extracted = extract_metadata_from_body(node["body"])
                if extracted.get("depends_on_refs"):
                    meta["depends_on_refs"] = extracted["depends_on_refs"]
                    node = {**node, "metadata": meta}
            if meta.get("depends_on_refs"):
                link_depends_on_from_metadata(self, node, session_id)

        edges = self.list_edges(session_id=session_id)
        return {"nodes": nodes, "edges": edges}

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

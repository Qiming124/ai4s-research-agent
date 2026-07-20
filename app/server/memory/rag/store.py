# =============================================================================
# Chroma 向量库 + SQLite 文档元数据注册表。
#
# 职责：
#     1. 文档切块、嵌入并写入 Chroma collection（按 project rag_namespace 隔离）
#     2. SQLite 维护 doc_id、hash、标题等元数据
#     3. 检索、删除、purge 与 namespace 解析
#
# 架构位置：
#     - 被调用：server/api/documents.py、memory/rag/retrieval.py、mcp/servers/rag.py
#     - 调用：memory/rag/chunking.py、embeddings.py、server/config.py
#
# 阅读提示：
#     - 新人先看 RagStore.add_document、search、resolve_rag_project_id
#
# Debug：
#     - Chroma 锁 → 多进程同时写，检查 threading 与 persist 目录
#     - 检索跨课题 → rag_namespace 与 project_id 映射错误
# =============================================================================

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb

from server.config import Settings, get_settings
from server.memory.rag.chunking import chunk_text
from server.memory.rag.embeddings import get_embedding_function

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "ai4s_documents"


def doc_id_from_file_path(path: Path, scope_id: str) -> str:
    """由课题/会话 scope + 文件绝对路径生成稳定 doc_id。"""
    resolved = path.resolve()
    payload = f"{scope_id}:{resolved}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"file-{digest}"


def resolve_rag_project_id(session_id: str | None = None, project_id: str | None = None) -> str:
    """解析 RAG 课题命名空间：显式 project_id 优先，否则由会话反查。"""
    if project_id and project_id.strip():
        return project_id.strip()
    if session_id and session_id.strip():
        try:
            from server.memory.projects import get_project_store

            return get_project_store().get_project_for_session(session_id.strip())
        except Exception:
            return "default"
    return "default"


_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_documents (
    doc_id       TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL DEFAULT '__legacy__',
    project_id   TEXT NOT NULL DEFAULT 'default',
    title        TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_deleted_sources (
    session_id   TEXT NOT NULL,
    source_path  TEXT NOT NULL,
    deleted_at   TEXT NOT NULL,
    PRIMARY KEY (session_id, source_path)
);
"""


@dataclass
class DocumentRecord:
    doc_id: str
    session_id: str
    title: str
    source: str
    chunk_count: int
    created_at: str
    project_id: str = "default"


@dataclass
class RetrievedSnippet:
    doc_id: str
    session_id: str
    title: str
    source: str
    content: str
    score: float | None = None
    project_id: str = "default"


class RagStore:
    """L3 向量记忆：Chroma 存 chunk，SQLite 存文档元数据（按 session 隔离）。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        embedding_provider: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._chroma_path = Path(self._settings.rag_chroma_path)
        self._chroma_path.mkdir(parents=True, exist_ok=True)
        self._check_chroma_writable()
        self._registry_path = self._chroma_path / "registry.db"
        self._embedding_fn = get_embedding_function(
            self._settings,
            provider=embedding_provider,
        )
        self._client = chromadb.PersistentClient(path=str(self._chroma_path))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._lock = threading.Lock()
        self._registry_conn = sqlite3.connect(
            str(self._registry_path),
            check_same_thread=False,
        )
        self._registry_conn.row_factory = sqlite3.Row
        with self._lock:
            self._registry_conn.executescript(_REGISTRY_SCHEMA)
            self._migrate_registry_schema()
            self._registry_conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_documents_session
                    ON rag_documents(session_id)
                """,
            )
            self._registry_conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_documents_project
                    ON rag_documents(project_id)
                """,
            )
            self._registry_conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _migrate_registry_schema(self) -> None:
        """兼容旧 registry：补 session_id / project_id 列、重建 rag_deleted_sources。"""
        cols = {
            row[1]
            for row in self._registry_conn.execute(
                "PRAGMA table_info(rag_documents)",
            ).fetchall()
        }
        if "session_id" not in cols:
            self._registry_conn.execute(
                "ALTER TABLE rag_documents ADD COLUMN session_id TEXT NOT NULL DEFAULT '__legacy__'",
            )
        if "project_id" not in cols:
            self._registry_conn.execute(
                "ALTER TABLE rag_documents ADD COLUMN project_id TEXT NOT NULL DEFAULT 'default'",
            )
            # 按会话反查课题，回填 project_id
            try:
                from server.memory.projects import get_project_store

                proj = get_project_store()
                rows = self._registry_conn.execute(
                    "SELECT DISTINCT session_id FROM rag_documents"
                ).fetchall()
                for row in rows:
                    sid = row["session_id"]
                    pid = proj.get_project_for_session(sid) if sid and sid != "__legacy__" else "default"
                    self._registry_conn.execute(
                        "UPDATE rag_documents SET project_id = ? WHERE session_id = ?",
                        (pid, sid),
                    )
            except Exception:
                logger.debug("RAG project_id 回填跳过", exc_info=True)
        deleted_cols = {
            row[1]
            for row in self._registry_conn.execute(
                "PRAGMA table_info(rag_deleted_sources)",
            ).fetchall()
        }
        if deleted_cols and "session_id" not in deleted_cols:
            self._registry_conn.execute(
                "ALTER TABLE rag_deleted_sources RENAME TO rag_deleted_sources_old",
            )
            self._registry_conn.executescript(
                """
                CREATE TABLE rag_deleted_sources (
                    session_id   TEXT NOT NULL,
                    source_path  TEXT NOT NULL,
                    deleted_at   TEXT NOT NULL,
                    PRIMARY KEY (session_id, source_path)
                );
                INSERT INTO rag_deleted_sources (session_id, source_path, deleted_at)
                SELECT '__legacy__', source_path, deleted_at
                FROM rag_deleted_sources_old;
                DROP TABLE rag_deleted_sources_old;
                """
            )

    def _check_chroma_writable(self) -> None:
        probe = self._chroma_path / ".write_probe"
        try:
            probe.touch()
            probe.unlink(missing_ok=True)
        except OSError:
            logger.error(
                "RAG 目录不可写: %s；删除/索引会失败。请停止服务后执行 "
                "sudo chown -R $(whoami):$(whoami) %s 或 sudo rm -rf %s",
                self._chroma_path,
                self._chroma_path,
                self._chroma_path,
            )

    def _normalize_source_path(self, source: str) -> str | None:
        if not source.strip():
            return None
        try:
            return str(Path(source).resolve())
        except OSError:
            return source.strip()

    def _mark_source_deleted(self, session_id: str, source: str) -> None:
        normalized = self._normalize_source_path(source)
        if not normalized:
            return
        with self._lock:
            self._registry_conn.execute(
                """
                INSERT OR REPLACE INTO rag_deleted_sources
                    (session_id, source_path, deleted_at)
                VALUES (?, ?, ?)
                """,
                (session_id, normalized, self._now_iso()),
            )
            self._registry_conn.commit()

    def _unmark_source_deleted(self, session_id: str, source: str) -> None:
        normalized = self._normalize_source_path(source)
        if not normalized:
            return
        with self._lock:
            self._registry_conn.execute(
                """
                DELETE FROM rag_deleted_sources
                WHERE session_id = ? AND source_path = ?
                """,
                (session_id, normalized),
            )
            self._registry_conn.commit()

    def _is_source_deleted(self, session_id: str, path: Path) -> bool:
        normalized = str(path.resolve())
        with self._lock:
            row = self._registry_conn.execute(
                """
                SELECT 1 FROM rag_deleted_sources
                WHERE session_id = ? AND source_path = ?
                """,
                (session_id, normalized),
            ).fetchone()
        return row is not None

    def _iter_mcp_file_paths(self) -> list[Path]:
        allowed = self._settings.mcp_allowed_dirs
        roots = [Path(p.strip()) for p in allowed.split(":") if p.strip()]
        paths: list[Path] = []
        patterns = ("*.md", "*.txt", "*.markdown")
        for root in roots:
            if not root.exists():
                continue
            for pattern in patterns:
                for path in root.rglob(pattern):
                    if path.is_file():
                        paths.append(path)
        return paths

    def _mark_all_mcp_sources_deleted(self, session_id: str) -> None:
        for path in self._iter_mcp_file_paths():
            self._mark_source_deleted(session_id, str(path))

    def add_document(
        self,
        content: str,
        *,
        session_id: str,
        title: str | None = None,
        source: str = "",
        doc_id: str | None = None,
        project_id: str | None = None,
    ) -> DocumentRecord:
        session_id = session_id.strip()
        if not session_id:
            raise ValueError("session_id 不能为空")
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)

        chunks = chunk_text(
            content,
            chunk_size=self._settings.rag_chunk_size,
            chunk_overlap=self._settings.rag_chunk_overlap,
        )
        if not chunks:
            raise ValueError("文档内容为空，无法索引")

        resolved_id = doc_id or str(uuid.uuid4())
        resolved_title = (title or source or resolved_id).strip() or resolved_id

        with self._lock:
            row = self._registry_conn.execute(
                """
                SELECT created_at FROM rag_documents
                WHERE doc_id = ? AND project_id = ?
                """,
                (resolved_id, pid),
            ).fetchone()
            created_at = row["created_at"] if row else self._now_iso()

        ids = [f"{pid}::{resolved_id}::{idx}" for idx in range(len(chunks))]
        metadatas = [
            {
                "session_id": session_id,
                "project_id": pid,
                "doc_id": resolved_id,
                "chunk_index": idx,
                "title": resolved_title,
                "source": source,
            }
            for idx in range(len(chunks))
        ]

        with self._lock:
            self._delete_chroma_chunks(resolved_id, session_id, project_id=pid)

            self._collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas,
            )

            self._registry_conn.execute(
                """
                INSERT OR REPLACE INTO rag_documents
                    (doc_id, session_id, project_id, title, source, chunk_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_id,
                    session_id,
                    pid,
                    resolved_title,
                    source,
                    len(chunks),
                    created_at,
                ),
            )
            self._registry_conn.commit()

        logger.info(
            "RAG indexed project=%s session=%s doc_id=%s title=%s chunks=%d",
            pid,
            session_id,
            resolved_id,
            resolved_title,
            len(chunks),
        )
        return DocumentRecord(
            doc_id=resolved_id,
            session_id=session_id,
            project_id=pid,
            title=resolved_title,
            source=source,
            chunk_count=len(chunks),
            created_at=created_at,
        )

    def _cleanup_legacy_file_duplicates(
        self,
        resolved: Path,
        stable_id: str,
        session_id: str,
    ) -> None:
        with self._lock:
            rows = self._registry_conn.execute(
                """
                SELECT doc_id, source FROM rag_documents
                WHERE session_id = ? AND doc_id != ?
                """,
                (session_id, stable_id),
            ).fetchall()
        for row in rows:
            source = row["source"]
            if not source:
                continue
            try:
                if Path(source).resolve() == resolved:
                    self.delete_document(row["doc_id"], session_id=session_id)
            except OSError:
                continue

    def add_file(
        self,
        path: Path,
        *,
        session_id: str,
        title: str | None = None,
        project_id: str | None = None,
    ) -> DocumentRecord:
        session_id = session_id.strip()
        if not session_id:
            raise ValueError("session_id 不能为空")
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)

        resolved = path.resolve()
        stable_id = doc_id_from_file_path(resolved, pid)
        self._unmark_source_deleted(session_id, str(resolved))
        self._cleanup_legacy_file_duplicates(resolved, stable_id, session_id)
        text = resolved.read_text(encoding="utf-8")
        return self.add_document(
            text,
            session_id=session_id,
            project_id=pid,
            title=title or resolved.name,
            source=str(resolved),
            doc_id=stable_id,
        )

    def _row_to_record(self, row: sqlite3.Row) -> DocumentRecord:
        keys = row.keys()
        return DocumentRecord(
            doc_id=row["doc_id"],
            session_id=row["session_id"],
            project_id=row["project_id"] if "project_id" in keys else "default",
            title=row["title"],
            source=row["source"],
            chunk_count=row["chunk_count"],
            created_at=row["created_at"],
        )

    def list_documents(
        self,
        session_id: str | None = None,
        *,
        project_id: str | None = None,
    ) -> list[DocumentRecord]:
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)
        with self._lock:
            rows = self._registry_conn.execute(
                """
                SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                FROM rag_documents
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (pid,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_document(
        self,
        doc_id: str,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> DocumentRecord | None:
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id) if (session_id or project_id) else None
        with self._lock:
            if pid:
                row = self._registry_conn.execute(
                    """
                    SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                    FROM rag_documents WHERE doc_id = ? AND project_id = ?
                    """,
                    (doc_id, pid),
                ).fetchone()
            elif session_id:
                row = self._registry_conn.execute(
                    """
                    SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                    FROM rag_documents WHERE doc_id = ? AND session_id = ?
                    """,
                    (doc_id, session_id),
                ).fetchone()
            else:
                row = self._registry_conn.execute(
                    """
                    SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                    FROM rag_documents WHERE doc_id = ?
                    """,
                    (doc_id,),
                ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def _delete_chroma_chunks(
        self,
        doc_id: str,
        session_id: str,
        *,
        project_id: str | None = None,
    ) -> None:
        pid = project_id or resolve_rag_project_id(session_id=session_id)
        try:
            existing = self._collection.get(
                where={
                    "$or": [
                        {"$and": [{"doc_id": doc_id}, {"project_id": pid}]},
                        {"$and": [{"doc_id": doc_id}, {"session_id": session_id}]},
                    ]
                },
            )
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:
            logger.exception(
                "RAG Chroma 删除 chunk 失败 project=%s session=%s doc_id=%s，将继续清理 registry",
                pid,
                session_id,
                doc_id,
            )

    def _recreate_collection(self) -> None:
        try:
            self._client.delete_collection(_COLLECTION_NAME)
        except Exception:
            logger.debug("RAG collection 不存在或删除失败，将直接重建", exc_info=True)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def delete_document(
        self,
        doc_id: str,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> bool:
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id) if (session_id or project_id) else None
        with self._lock:
            if pid:
                row = self._registry_conn.execute(
                    """
                    SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                    FROM rag_documents WHERE doc_id = ? AND project_id = ?
                    """,
                    (doc_id, pid),
                ).fetchone()
            elif session_id:
                row = self._registry_conn.execute(
                    """
                    SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                    FROM rag_documents WHERE doc_id = ? AND session_id = ?
                    """,
                    (doc_id, session_id),
                ).fetchone()
            else:
                row = self._registry_conn.execute(
                    """
                    SELECT doc_id, session_id, project_id, title, source, chunk_count, created_at
                    FROM rag_documents WHERE doc_id = ?
                    """,
                    (doc_id,),
                ).fetchone()
            if row is None:
                return False

            sid = row["session_id"]
            source = row["source"]
            row_pid = row["project_id"] if "project_id" in row.keys() else pid
            self._delete_chroma_chunks(doc_id, sid, project_id=row_pid)

            self._registry_conn.execute(
                "DELETE FROM rag_documents WHERE doc_id = ? AND session_id = ?",
                (doc_id, sid),
            )
            self._registry_conn.commit()

        if source:
            self._mark_source_deleted(sid, source)
        return True

    def clear_session_documents(self, session_id: str) -> int:
        """删除指定会话上传的 RAG 文档（不影响同课题其它会话上传的文档）。"""
        session_id = session_id.strip()
        if not session_id:
            return 0
        with self._lock:
            rows = self._registry_conn.execute(
                """
                SELECT doc_id, session_id FROM rag_documents WHERE session_id = ?
                """,
                (session_id,),
            ).fetchall()
        count = 0
        for row in rows:
            if self.delete_document(row["doc_id"], session_id=session_id):
                count += 1
        logger.info("RAG 已清空会话上传文档 session=%s count=%d", session_id, count)
        return count

    def clear_project_documents(self, project_id: str) -> int:
        """删除指定课题的全部 RAG 文档。"""
        pid = (project_id or "").strip() or "default"
        records = self.list_documents(project_id=pid)
        for record in records:
            self.delete_document(record.doc_id, session_id=record.session_id, project_id=pid)
        logger.info("RAG 已清空课题文档 project=%s count=%d", pid, len(records))
        return len(records)

    def clear_all_documents(self) -> int:
        """清空全部 RAG 文档（Chroma collection + registry）。"""
        with self._lock:
            row = self._registry_conn.execute(
                "SELECT COUNT(*) AS n FROM rag_documents",
            ).fetchone()
            count = int(row["n"]) if row else 0
            self._recreate_collection()
            self._registry_conn.execute("DELETE FROM rag_documents")
            self._registry_conn.execute("DELETE FROM rag_deleted_sources")
            self._registry_conn.commit()
        logger.info("RAG 已清空全部文档 count=%d", count)
        return count

    def retrieve(
        self,
        query: str,
        *,
        session_id: str,
        top_k: int | None = None,
        project_id: str | None = None,
    ) -> list[RetrievedSnippet]:
        session_id = session_id.strip()
        if not session_id:
            return []
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)

        normalized = query.strip()
        if not normalized:
            return []

        # 兼容旧向量（仅有 session_id）：纳入本课题下全部会话
        session_ids = [session_id]
        try:
            from server.memory.projects import get_project_store

            linked = get_project_store().list_sessions(pid)
            session_ids = list({s["session_id"] for s in linked} | {session_id})
        except Exception:
            pass

        k = top_k or self._settings.rag_retrieval_top_k
        where: dict[str, Any]
        if len(session_ids) == 1:
            where = {
                "$or": [
                    {"project_id": pid},
                    {"session_id": session_ids[0]},
                ]
            }
        else:
            where = {
                "$or": [
                    {"project_id": pid},
                    {"session_id": {"$in": session_ids}},
                ]
            }

        result = self._collection.query(
            query_texts=[normalized],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        snippets: list[RetrievedSnippet] = []
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        for doc, meta, dist in zip(documents[0], metadatas[0], distances[0]):
            if not doc or not meta:
                continue
            snippets.append(
                RetrievedSnippet(
                    doc_id=str(meta.get("doc_id", "")),
                    session_id=str(meta.get("session_id", session_id)),
                    project_id=str(meta.get("project_id", pid)),
                    title=str(meta.get("title", "")),
                    source=str(meta.get("source", "")),
                    content=doc,
                    score=float(dist) if dist is not None else None,
                )
            )
        return snippets

    def index_mcp_files(
        self,
        session_id: str,
        *,
        project_id: str | None = None,
    ) -> list[DocumentRecord]:
        """索引 MCP_ALLOWED_DIRS 下的文件到指定课题（跳过该会话已删除的源文件）。"""
        session_id = session_id.strip()
        if not session_id:
            return []
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)

        indexed: list[DocumentRecord] = []
        skipped = 0

        for path in self._iter_mcp_file_paths():
            if self._is_source_deleted(session_id, path):
                skipped += 1
                continue
            try:
                indexed.append(self.add_file(path, session_id=session_id, project_id=pid))
            except Exception:
                logger.exception(
                    "RAG 索引文件失败 project=%s session=%s path=%s",
                    pid,
                    session_id,
                    path,
                )

        if skipped:
            logger.info(
                "RAG 会话 %s 启动索引跳过 %d 个已删除 MCP 文件",
                session_id,
                skipped,
            )
        return indexed

    def ensure_mcp_files_indexed(
        self,
        session_id: str,
        *,
        project_id: str | None = None,
    ) -> list[DocumentRecord]:
        """若课题尚无 MCP 文件索引且配置启用，则按需索引。"""
        if not self._settings.rag_index_mcp_files:
            return []
        pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)
        if self.list_documents(session_id=session_id, project_id=pid):
            return []
        return self.index_mcp_files(session_id, project_id=pid)


_rag_store: RagStore | None = None


def get_rag_store() -> RagStore:
    global _rag_store
    if _rag_store is None:
        _rag_store = RagStore()
    return _rag_store


def reset_rag_store() -> None:
    global _rag_store
    _rag_store = None

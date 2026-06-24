# Chroma 向量库 + SQLite 文档元数据注册表。

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


def doc_id_from_file_path(path: Path) -> str:
    """由文件绝对路径生成稳定 doc_id，重启索引时覆盖而非重复插入。"""
    resolved = path.resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:32]
    return f"file-{digest}"


_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_documents (
    doc_id       TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_deleted_sources (
    source_path TEXT PRIMARY KEY,
    deleted_at  TEXT NOT NULL
);
"""


@dataclass
class DocumentRecord:
    doc_id: str
    title: str
    source: str
    chunk_count: int
    created_at: str


@dataclass
class RetrievedSnippet:
    doc_id: str
    title: str
    source: str
    content: str
    score: float | None = None


class RagStore:
    """L3 向量记忆：Chroma 存 chunk，SQLite 存文档元数据。"""

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
            self._registry_conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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

    def _mark_source_deleted(self, source: str) -> None:
        normalized = self._normalize_source_path(source)
        if not normalized:
            return
        with self._lock:
            self._registry_conn.execute(
                """
                INSERT OR REPLACE INTO rag_deleted_sources (source_path, deleted_at)
                VALUES (?, ?)
                """,
                (normalized, self._now_iso()),
            )
            self._registry_conn.commit()

    def _unmark_source_deleted(self, source: str) -> None:
        normalized = self._normalize_source_path(source)
        if not normalized:
            return
        with self._lock:
            self._registry_conn.execute(
                "DELETE FROM rag_deleted_sources WHERE source_path = ?",
                (normalized,),
            )
            self._registry_conn.commit()

    def _is_source_deleted(self, path: Path) -> bool:
        normalized = str(path.resolve())
        with self._lock:
            row = self._registry_conn.execute(
                "SELECT 1 FROM rag_deleted_sources WHERE source_path = ?",
                (normalized,),
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

    def _mark_all_mcp_sources_deleted(self) -> None:
        for path in self._iter_mcp_file_paths():
            self._mark_source_deleted(str(path))

    def add_document(
        self,
        content: str,
        *,
        title: str | None = None,
        source: str = "",
        doc_id: str | None = None,
    ) -> DocumentRecord:
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
                "SELECT created_at FROM rag_documents WHERE doc_id = ?",
                (resolved_id,),
            ).fetchone()
            created_at = row["created_at"] if row else self._now_iso()

        ids = [f"{resolved_id}::{idx}" for idx in range(len(chunks))]
        metadatas = [
            {
                "doc_id": resolved_id,
                "chunk_index": idx,
                "title": resolved_title,
                "source": source,
            }
            for idx in range(len(chunks))
        ]

        with self._lock:
            # 若 doc_id 已存在，先删除旧 chunk
            self._delete_chroma_chunks(resolved_id)

            self._collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas,
            )

            self._registry_conn.execute(
                """
                INSERT OR REPLACE INTO rag_documents
                    (doc_id, title, source, chunk_count, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (resolved_id, resolved_title, source, len(chunks), created_at),
            )
            self._registry_conn.commit()

        logger.info(
            "RAG indexed doc_id=%s title=%s chunks=%d",
            resolved_id,
            resolved_title,
            len(chunks),
        )
        return DocumentRecord(
            doc_id=resolved_id,
            title=resolved_title,
            source=source,
            chunk_count=len(chunks),
            created_at=created_at,
        )

    def _cleanup_legacy_file_duplicates(self, resolved: Path, stable_id: str) -> None:
        """删除同一物理文件在旧逻辑下产生的 UUID doc_id 副本。"""
        with self._lock:
            rows = self._registry_conn.execute(
                "SELECT doc_id, source FROM rag_documents WHERE doc_id != ?",
                (stable_id,),
            ).fetchall()
        for row in rows:
            source = row["source"]
            if not source:
                continue
            try:
                if Path(source).resolve() == resolved:
                    self.delete_document(row["doc_id"])
            except OSError:
                continue

    def add_file(self, path: Path, *, title: str | None = None) -> DocumentRecord:
        resolved = path.resolve()
        stable_id = doc_id_from_file_path(resolved)
        self._unmark_source_deleted(str(resolved))
        self._cleanup_legacy_file_duplicates(resolved, stable_id)
        text = resolved.read_text(encoding="utf-8")
        return self.add_document(
            text,
            title=title or resolved.name,
            source=str(resolved),
            doc_id=stable_id,
        )

    def list_documents(self) -> list[DocumentRecord]:
        with self._lock:
            rows = self._registry_conn.execute(
                """
                SELECT doc_id, title, source, chunk_count, created_at
                FROM rag_documents
                ORDER BY created_at DESC
                """,
            ).fetchall()
        return [
            DocumentRecord(
                doc_id=row["doc_id"],
                title=row["title"],
                source=row["source"],
                chunk_count=row["chunk_count"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_document(self, doc_id: str) -> DocumentRecord | None:
        with self._lock:
            row = self._registry_conn.execute(
                """
                SELECT doc_id, title, source, chunk_count, created_at
                FROM rag_documents WHERE doc_id = ?
                """,
                (doc_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentRecord(
            doc_id=row["doc_id"],
            title=row["title"],
            source=row["source"],
            chunk_count=row["chunk_count"],
            created_at=row["created_at"],
        )

    def _delete_chroma_chunks(self, doc_id: str) -> None:
        """删除 Chroma 中某文档的全部 chunk；失败时记录日志但不阻断 registry 清理。"""
        try:
            existing = self._collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:
            logger.exception(
                "RAG Chroma 删除 chunk 失败 doc_id=%s，将继续清理 registry",
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

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            row = self._registry_conn.execute(
                """
                SELECT doc_id, title, source, chunk_count, created_at
                FROM rag_documents WHERE doc_id = ?
                """,
                (doc_id,),
            ).fetchone()
            if row is None:
                return False

            source = row["source"]
            self._delete_chroma_chunks(doc_id)

            self._registry_conn.execute(
                "DELETE FROM rag_documents WHERE doc_id = ?",
                (doc_id,),
            )
            self._registry_conn.commit()

        if source:
            self._mark_source_deleted(source)
        return True

    def clear_all_documents(self) -> int:
        """清空全部 RAG 文档（Chroma collection + registry）。"""
        with self._lock:
            row = self._registry_conn.execute(
                "SELECT COUNT(*) AS n FROM rag_documents",
            ).fetchone()
            count = int(row["n"]) if row else 0
            self._recreate_collection()
            self._registry_conn.execute("DELETE FROM rag_documents")
            self._registry_conn.commit()
        self._mark_all_mcp_sources_deleted()
        logger.info("RAG 已清空全部文档 count=%d", count)
        return count

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedSnippet]:
        normalized = query.strip()
        if not normalized:
            return []

        k = top_k or self._settings.rag_retrieval_top_k
        result = self._collection.query(
            query_texts=[normalized],
            n_results=k,
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
                    title=str(meta.get("title", "")),
                    source=str(meta.get("source", "")),
                    content=doc,
                    score=float(dist) if dist is not None else None,
                )
            )
        return snippets

    def index_mcp_files(self) -> list[DocumentRecord]:
        """索引 MCP_ALLOWED_DIRS 下的 .md / .txt 文件（跳过用户已删除的源文件）。"""
        indexed: list[DocumentRecord] = []
        skipped = 0

        for path in self._iter_mcp_file_paths():
            if self._is_source_deleted(path):
                skipped += 1
                logger.debug("RAG 跳过已删除的 MCP 文件: %s", path)
                continue
            try:
                indexed.append(self.add_file(path))
            except Exception:
                logger.exception("RAG 索引文件失败: %s", path)

        if skipped:
            logger.info("RAG 启动索引跳过 %d 个已删除 MCP 文件", skipped)
        return indexed


_rag_store: RagStore | None = None


def get_rag_store() -> RagStore:
    global _rag_store
    if _rag_store is None:
        _rag_store = RagStore()
    return _rag_store


def reset_rag_store() -> None:
    global _rag_store
    _rag_store = None

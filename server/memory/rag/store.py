# Chroma 向量库 + SQLite 文档元数据注册表。

from __future__ import annotations

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

_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_documents (
    doc_id       TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
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
        created_at = self._now_iso()

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
            existing = self._collection.get(where={"doc_id": resolved_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])

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

    def add_file(self, path: Path, *, title: str | None = None) -> DocumentRecord:
        text = path.read_text(encoding="utf-8")
        return self.add_document(
            text,
            title=title or path.name,
            source=str(path),
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

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            row = self._registry_conn.execute(
                "SELECT 1 FROM rag_documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            if row is None:
                return False

            existing = self._collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])

            self._registry_conn.execute(
                "DELETE FROM rag_documents WHERE doc_id = ?",
                (doc_id,),
            )
            self._registry_conn.commit()
        return True

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
        """索引 MCP_ALLOWED_DIRS 下的 .md / .txt 文件。"""
        allowed = self._settings.mcp_allowed_dirs
        roots = [Path(p.strip()) for p in allowed.split(":") if p.strip()]
        indexed: list[DocumentRecord] = []
        patterns = ("*.md", "*.txt", "*.markdown")

        for root in roots:
            if not root.exists():
                continue
            for pattern in patterns:
                for path in root.rglob(pattern):
                    if path.is_file():
                        try:
                            indexed.append(self.add_file(path))
                        except Exception:
                            logger.exception("RAG 索引文件失败: %s", path)
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

"""RAG test embedding provider 与结构化记忆存储。"""

import tempfile
from pathlib import Path

from server.config import Settings
from server.memory.rag.store import RagStore, doc_id_from_file_path
from server.memory.structured.store import StructuredMemoryStore

_SESSION = "test-session-a"
_SESSION_B = "test-session-b"


def test_structured_memory_crud():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        store = StructuredMemoryStore(db_path)
        entry = store.create_entry(
            session_id="sess-1",
            kind="hypothesis",
            title="H1",
            body="Loss has local minima near zero.",
            metadata={"source": "unit-test"},
        )
        assert entry["id"] is not None
        assert entry["kind"] == "hypothesis"

        listed = store.list_entries(session_id="sess-1")
        assert len(listed) == 1
        assert listed[0]["body"] == "Loss has local minima near zero."


def test_rag_test_embedding_provider_allowed():
    settings = Settings(
        deepseek_api_key="sk-test",
        rag_embedding_provider="test",
    )
    assert settings.rag_embedding_provider == "test"


def test_clear_session_documents():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
        )
        store = RagStore(settings, embedding_provider="test")
        store.add_document("alpha content", session_id=_SESSION, title="Alpha")
        store.add_document("beta content", session_id=_SESSION, title="Beta")
        assert len(store.list_documents(_SESSION)) == 2

        deleted = store.clear_session_documents(_SESSION)
        assert deleted == 2
        assert store.list_documents(_SESSION) == []


def test_clear_all_documents():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
        )
        store = RagStore(settings, embedding_provider="test")
        store.add_document("alpha content", session_id=_SESSION, title="Alpha")
        store.add_document("beta content", session_id=_SESSION_B, title="Beta")
        assert len(store.list_documents(_SESSION)) == 1
        assert len(store.list_documents(_SESSION_B)) == 1

        deleted = store.clear_all_documents()
        assert deleted == 2
        assert store.list_documents(_SESSION) == []
        assert store.list_documents(_SESSION_B) == []


def test_session_isolation():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
        )
        store = RagStore(settings, embedding_provider="test")
        store.add_document(
            "session A secret keyword xyzzy",
            session_id=_SESSION,
            title="A-doc",
            doc_id="doc-a",
        )
        store.add_document(
            "session B secret keyword plugh",
            session_id=_SESSION_B,
            title="B-doc",
            doc_id="doc-b",
        )

        hits_a = store.retrieve("xyzzy", session_id=_SESSION, top_k=4)
        hits_b = store.retrieve("plugh", session_id=_SESSION_B, top_k=4)

        assert any(s.doc_id == "doc-a" for s in hits_a)
        assert not any(s.doc_id == "doc-b" for s in hits_a)
        assert any(s.doc_id == "doc-b" for s in hits_b)
        assert not any(s.doc_id == "doc-a" for s in hits_b)


def test_delete_document_clears_registry_even_if_chroma_delete_fails():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
        )
        store = RagStore(settings, embedding_provider="test")
        record = store.add_document(
            "orphan test",
            session_id=_SESSION,
            title="Orphan",
        )

        def _boom(**_kwargs: object) -> None:
            raise RuntimeError("chroma unavailable")

        store._collection.delete = _boom  # type: ignore[method-assign]
        assert store.delete_document(record.doc_id, session_id=_SESSION) is True
        assert store.list_documents(_SESSION) == []


def test_add_file_stable_doc_id_on_reindex():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
        )
        store = RagStore(settings, embedding_provider="test")
        file_path = Path(tmp) / "note.txt"
        file_path.write_text("hello rag stable id", encoding="utf-8")

        first = store.add_file(file_path, session_id=_SESSION)
        second = store.add_file(file_path, session_id=_SESSION)

        assert first.doc_id == second.doc_id
        assert first.doc_id == doc_id_from_file_path(file_path.resolve(), _SESSION)
        assert len(store.list_documents(_SESSION)) == 1
        assert store.list_documents(_SESSION)[0].chunk_count == 1


def test_deleted_mcp_file_not_reindexed_on_startup():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        mcp_root = Path(tmp) / "mcp_files"
        mcp_root.mkdir()
        note = mcp_root / "note.txt"
        note.write_text("mcp auto index content", encoding="utf-8")

        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
            mcp_allowed_dirs=str(mcp_root),
        )
        store = RagStore(settings, embedding_provider="test")

        indexed = store.index_mcp_files(_SESSION)
        assert len(indexed) == 1
        doc_id = indexed[0].doc_id

        assert store.delete_document(doc_id, session_id=_SESSION) is True
        assert store.list_documents(_SESSION) == []

        reindexed = store.index_mcp_files(_SESSION)
        assert reindexed == []
        assert store.list_documents(_SESSION) == []


def test_clear_session_blocks_mcp_reindex():
    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        mcp_root = Path(tmp) / "mcp_files"
        mcp_root.mkdir()
        (mcp_root / "a.txt").write_text("alpha", encoding="utf-8")
        (mcp_root / "b.txt").write_text("beta", encoding="utf-8")

        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(chroma_path),
            mcp_allowed_dirs=str(mcp_root),
        )
        store = RagStore(settings, embedding_provider="test")
        assert len(store.index_mcp_files(_SESSION)) == 2

        assert store.clear_session_documents(_SESSION) == 2
        assert store.list_documents(_SESSION) == []

        reindexed = store.index_mcp_files(_SESSION)
        assert reindexed == []
        assert store.list_documents(_SESSION) == []

"""RAG test embedding provider 与结构化记忆存储。"""

import tempfile
from pathlib import Path

from server.config import Settings
from server.memory.rag.store import RagStore, doc_id_from_file_path
from server.memory.structured.store import StructuredMemoryStore


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

        first = store.add_file(file_path)
        second = store.add_file(file_path)

        assert first.doc_id == second.doc_id
        assert first.doc_id == doc_id_from_file_path(file_path.resolve())
        assert len(store.list_documents()) == 1
        assert store.list_documents()[0].chunk_count == 1

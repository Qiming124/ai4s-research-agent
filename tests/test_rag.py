"""Task 6: L3 RAG vector memory — ingestion, retrieval, API, agent integration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.agents.subagent import SubAgent
from server.main import app
from server.memory.rag.chunking import chunk_text
from server.memory.rag.retrieval import format_rag_context, retrieve_for_query
from server.memory.rag.session_refs import SessionRagRefStore
from server.memory.rag.store import RagStore, reset_rag_store
from server.memory.session import reset_session_store
from shared.schemas import StreamChunk


@pytest.fixture
def rag_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    chroma_path = tmp_path / "chroma"
    db_path = tmp_path / "sessions.db"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ENABLE_RAG", "true")
    monkeypatch.setenv("RAG_CHROMA_PATH", str(chroma_path))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "test")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "memory")
    monkeypatch.setenv("SESSION_DB_PATH", str(db_path))
    monkeypatch.setenv("ENABLE_MCP", "false")

    from server.config import get_settings
    from server.mcp.client import reset_mcp_client
    from server.memory.manager import reset_memory_manager

    get_settings.cache_clear()
    reset_rag_store()
    reset_mcp_client()
    reset_session_store()
    reset_memory_manager()
    yield chroma_path
    reset_rag_store()
    reset_mcp_client()
    reset_session_store()
    reset_memory_manager()
    get_settings.cache_clear()


@pytest.fixture
def rag_client(rag_env: Path) -> TestClient:
    return TestClient(app)


def test_chunk_text_overlap() -> None:
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=400, chunk_overlap=50)
    assert len(chunks) >= 2
    assert all(len(c) <= 400 for c in chunks)


def test_rag_store_ingest_and_retrieve(rag_env: Path) -> None:
    from server.config import get_settings

    store = RagStore(get_settings(), embedding_provider="test")
    record = store.add_document(
        "Adam optimizer uses adaptive learning rates for neural network training.",
        title="Adam Notes",
        source="notes.md",
        doc_id="doc-adam",
    )
    assert record.doc_id == "doc-adam"
    assert record.chunk_count == 1

    snippets = store.retrieve("Adam optimizer learning rate")
    assert len(snippets) >= 1
    assert snippets[0].doc_id == "doc-adam"
    assert "Adam" in snippets[0].content


def test_rag_store_list_and_delete(rag_env: Path) -> None:
    from server.config import get_settings

    store = RagStore(get_settings(), embedding_provider="test")
    store.add_document("content one", title="One", doc_id="doc-1")
    store.add_document("content two", title="Two", doc_id="doc-2")

    docs = store.list_documents()
    assert len(docs) == 2

    assert store.delete_document("doc-1")
    assert store.get_document("doc-1") is None
    assert len(store.list_documents()) == 1


def test_format_rag_context() -> None:
    from server.memory.rag.store import RetrievedSnippet

    text = format_rag_context(
        [
            RetrievedSnippet(
                doc_id="d1",
                title="Paper",
                source="paper.md",
                content="Important finding about SGD.",
            ),
        ]
    )
    assert "Paper" in text
    assert "paper.md" in text
    assert "Important finding" in text


def test_session_rag_refs(rag_env: Path, tmp_path: Path) -> None:
    db = tmp_path / "refs.db"
    store = SessionRagRefStore(db)
    store.add_ref("sess-1", "doc-a", "snippet preview about Adam")
    refs = store.get_refs("sess-1")
    assert len(refs) == 1
    assert refs[0]["doc_id"] == "doc-a"
    assert "Adam" in refs[0]["snippet"]


def test_documents_api_upload_and_list(rag_client: TestClient) -> None:
    resp = rag_client.post(
        "/v1/documents",
        json={
            "content": "Transformer architecture uses self-attention mechanisms.",
            "title": "Transformer",
            "doc_id": "doc-transformer",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["doc_id"] == "doc-transformer"
    assert data["status"] == "indexed"

    list_resp = rag_client.get("/v1/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()["documents"]
    assert any(d["doc_id"] == "doc-transformer" for d in docs)


def test_documents_api_delete(rag_client: TestClient) -> None:
    rag_client.post(
        "/v1/documents",
        json={"content": "temporary doc", "title": "Temp", "doc_id": "doc-temp"},
    )
    del_resp = rag_client.delete("/v1/documents/doc-temp")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    missing = rag_client.delete("/v1/documents/doc-temp")
    assert missing.status_code == 404


def test_documents_api_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ENABLE_RAG", "false")
    from server.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.post("/v1/documents", json={"content": "x"})
    assert resp.status_code == 400
    get_settings.cache_clear()


def test_session_rag_refs_api(rag_client: TestClient, tmp_path: Path) -> None:
    from server.config import get_settings

    settings = get_settings()
    store = SessionRagRefStore(settings.session_db_path)
    store.add_ref("sess-rag", "doc-ref", "preview snippet")

    resp = rag_client.get("/v1/sessions/sess-rag/rag-refs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-rag"
    assert data["refs"][0]["doc_id"] == "doc-ref"


@pytest.mark.asyncio
async def test_subagent_injects_rag_context(rag_env: Path) -> None:
    from server.config import get_settings

    settings = get_settings()
    store = RagStore(settings, embedding_provider="test")
    store.add_document(
        "The AI4S benchmark document mentions unique phrase ZETA-42 for retrieval.",
        title="Benchmark Doc",
        doc_id="bench-doc",
    )

    captured_prompts: list[str] = []

    class FakeLLM:
        async def stream_chat(self, messages):
            captured_prompts.append(messages[0]["content"])
            yield StreamChunk(type="content", content="answer")
            yield StreamChunk(type="done", content="")

    agent = SubAgent("literature", settings=settings, llm_client=FakeLLM())
    async for _ in agent.run(
        "What does the benchmark document say about ZETA-42?",
        "sess-lit",
        persist_session=False,
    ):
        pass

    assert captured_prompts
    assert "ZETA-42" in captured_prompts[0]
    assert "Benchmark Doc" in captured_prompts[0]


@pytest.mark.asyncio
async def test_subagent_skips_rag_for_general(rag_env: Path) -> None:
    from server.config import get_settings

    settings = get_settings()
    store = RagStore(settings, embedding_provider="test")
    store.add_document("secret RAG content SIGMA-99", title="Secret", doc_id="sec")

    captured: list[str] = []

    class FakeLLM:
        async def stream_chat(self, messages):
            captured.append(messages[0]["content"])
            yield StreamChunk(type="done", content="")

    agent = SubAgent("general", settings=settings, llm_client=FakeLLM())
    async for _ in agent.run("query SIGMA-99", "sess-gen", persist_session=False):
        pass

    assert captured
    assert "SIGMA-99" not in captured[0]


def test_retrieve_for_query_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ENABLE_RAG", "false")
    from server.config import get_settings

    get_settings.cache_clear()
    assert retrieve_for_query("anything") == []
    get_settings.cache_clear()


def test_index_mcp_files(rag_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from server.config import get_settings

    mcp_dir = tmp_path / "mcp_files"
    mcp_dir.mkdir()
    (mcp_dir / "note.md").write_text("MCP file content about BATCH-NORM", encoding="utf-8")

    monkeypatch.setenv("MCP_ALLOWED_DIRS", str(mcp_dir))
    get_settings.cache_clear()

    store = RagStore(get_settings(), embedding_provider="test")
    indexed = store.index_mcp_files()
    assert len(indexed) == 1
    assert indexed[0].title == "note.md"

    snippets = store.retrieve("BATCH-NORM")
    assert snippets

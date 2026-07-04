"""GeneralAgent（legacy 编排）在 Math 模式下自动抽取定理。"""

import pytest

from server.agents.base import GeneralAgent
from server.config import Settings
from server.memory.manager import MemoryManager
from server.memory.session import InMemorySessionStore
from server.memory.structured import store as structured_store_module
from server.memory.structured.store import StructuredMemoryStore
from shared.schemas import StreamChunk


@pytest.mark.asyncio
async def test_general_agent_math_mode_persists_theorems(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions.db"
    settings = Settings(
        deepseek_api_key="sk-test",
        session_db_path=str(db_path),
        enable_mcp=False,
    )
    memory_store = StructuredMemoryStore(str(db_path))
    monkeypatch.setattr(structured_store_module, "_store", memory_store)

    class _FakeLlm:
        async def stream_chat(self, messages, **kwargs):
            yield StreamChunk(type="content", content="## 引理 1\n**陈述**：x=1。\n")
            yield StreamChunk(type="done", content="", usage={"total_tokens": 1})

    fake_llm = _FakeLlm()
    sessions = InMemorySessionStore()
    memory = MemoryManager(sessions, settings, fake_llm)  # type: ignore[arg-type]

    agent = GeneralAgent(
        settings=settings,
        llm_client=fake_llm,  # type: ignore[arg-type]
        session_store=sessions,
        memory_manager=memory,
        math_mode=True,
    )

    chunks = []
    session_id = ""
    async for chunk in agent.run("证明引理", None):
        chunks.append(chunk)
        if chunk.type == "done" and chunk.usage:
            session_id = chunk.usage.get("session_id", "")

    assert any(c.type == "done" for c in chunks)
    entries = memory_store.list_entries(session_id=session_id)
    assert len(entries) == 1
    assert "引理 1" in entries[0]["title"]

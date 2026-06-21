"""
API 集成测试（mock LLM/Agent，不调用真实 DeepSeek）。

运行：pytest tests/test_api.py -v
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.memory.session import get_session_store, reset_session_store
from shared.schemas import StreamChunk


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "memory")
    from server.config import get_settings

    get_settings.cache_clear()
    reset_session_store()
    from server.memory.manager import reset_memory_manager

    reset_memory_manager()
    yield TestClient(app)
    reset_session_store()
    reset_memory_manager()
    get_settings.cache_clear()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "model" in data


def test_get_session_404(client: TestClient) -> None:
    resp = client.get("/v1/sessions/nonexistent-id")
    assert resp.status_code == 404


def test_get_session_empty(client: TestClient) -> None:
    store = get_session_store()
    sid = store.create_session_id()
    store.get_or_create(sid)
    resp = client.get(f"/v1/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


def test_delete_session(client: TestClient) -> None:
    store = get_session_store()
    sid = store.create_session_id()
    from shared.schemas import ChatMessage

    store.append_message(sid, ChatMessage(role="user", content="hi"))
    resp = client.delete(f"/v1/sessions/{sid}")
    assert resp.status_code == 200
    assert client.get(f"/v1/sessions/{sid}").json()["messages"] == []


def test_chat_request_invalid_mode(client: TestClient) -> None:
    resp = client.post(
        "/v1/chat/stream",
        json={"message": "hello", "mode": "invalid"},
    )
    assert resp.status_code == 422


def test_chat_stream_mock(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgent:
        name = "general"

        async def run(
            self,
            message: str,
            session_id: str | None,
            *,
            system_prompt_override: str | None = None,
            max_history_messages: int | None = None,
            enable_history_summary: bool | None = None,
            enable_tools: bool | None = None,
        ) -> AsyncIterator[StreamChunk]:
            yield StreamChunk(type="content", content="mock reply", agent_name=self.name)
            yield StreamChunk(
                type="done",
                content="",
                usage={"total_tokens": 10},
                agent_name=self.name,
            )

    monkeypatch.setattr("server.api.chat.get_general_agent", lambda **_: FakeAgent())

    with client.stream(
        "POST",
        "/v1/chat/stream",
        json={"message": "hello", "session_id": "test-stream"},
    ) as resp:
        assert resp.status_code == 200
        body = resp.read().decode()

    assert '"type": "meta"' in body or '"type":"meta"' in body
    assert "agent_name" in body
    assert "mock reply" in body
    assert '"type": "done"' in body or '"type":"done"' in body


def test_chat_request_mode_math(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def fake_get_general_agent(*, math_mode: bool = False):
        calls.append(math_mode)

        class FakeAgent:
            name = "general"

            async def run(self, *args, **kwargs):
                yield StreamChunk(type="done", content="", agent_name="general")

        return FakeAgent()

    monkeypatch.setattr("server.api.chat.get_general_agent", fake_get_general_agent)

    with client.stream(
        "POST",
        "/v1/chat/stream",
        json={"message": "prove", "mode": "math"},
    ) as resp:
        assert resp.status_code == 200
        resp.read()

    assert calls == [True]


def test_chat_request_memory_overrides(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    class FakeAgent:
        name = "general"

        async def run(self, *args, **kwargs):
            captured.append(kwargs)
            yield StreamChunk(type="done", content="", agent_name="general")

    monkeypatch.setattr("server.api.chat.get_general_agent", lambda **_: FakeAgent())

    with client.stream(
        "POST",
        "/v1/chat/stream",
        json={
            "message": "hello",
            "max_history_messages": 8,
            "enable_history_summary": True,
        },
    ) as resp:
        assert resp.status_code == 200
        resp.read()

    assert captured[0]["max_history_messages"] == 8
    assert captured[0]["enable_history_summary"] is True


def test_stream_chunk_tool_fields() -> None:
    chunk = StreamChunk(
        type="tool_call_start",
        content='{"query":"adam"}',
        agent_name="general",
        tool_name="arxiv__search_papers",
        tool_call_id="call-1",
        a2a_task_id="task-99",
    )
    data = chunk.model_dump()
    assert data["type"] == "tool_call_start"
    assert data["tool_name"] == "arxiv__search_papers"
    assert data["tool_call_id"] == "call-1"
    assert data["a2a_task_id"] == "task-99"


def test_chat_stream_tool_events(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgent:
        name = "general"

        async def run(self, *args, **kwargs) -> AsyncIterator[StreamChunk]:
            yield StreamChunk(
                type="tool_call_start",
                content='{"query":"test"}',
                tool_name="web_search__search",
                tool_call_id="tc-1",
                agent_name=self.name,
            )
            yield StreamChunk(
                type="tool_call_result",
                content="search results",
                tool_name="web_search__search",
                tool_call_id="tc-1",
                agent_name=self.name,
            )
            yield StreamChunk(type="content", content="final", agent_name=self.name)
            yield StreamChunk(type="done", content="", agent_name=self.name)

    monkeypatch.setattr("server.api.chat.get_general_agent", lambda **_: FakeAgent())

    with client.stream(
        "POST",
        "/v1/chat/stream",
        json={"message": "search something", "session_id": "tool-test"},
    ) as resp:
        assert resp.status_code == 200
        body = resp.read().decode()

    assert "tool_call_start" in body
    assert "tool_call_result" in body
    assert "web_search__search" in body
    assert "final" in body


def test_session_reasoning_roundtrip_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shared.schemas import ChatMessage

    store = get_session_store()
    sid = store.create_session_id()
    store.get_or_create(sid)
    store.append_message(
        sid,
        ChatMessage(
            role="assistant",
            content="answer text",
            reasoning_content="deep thought",
        ),
    )

    resp = client.get(f"/v1/sessions/{sid}")
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["reasoning_content"] == "deep thought"
    assert messages[0]["content"] == "answer text"


def test_sqlite_session_api_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    db_path = tmp_path / "api_sessions.db"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SESSION_DB_PATH", str(db_path))

    from server.config import get_settings

    get_settings.cache_clear()
    reset_session_store()
    from server.memory.manager import reset_memory_manager

    reset_memory_manager()

    from server.main import app

    test_client = TestClient(app)

    class FakeAgent:
        name = "general"

        async def run(self, *args, **kwargs) -> AsyncIterator[StreamChunk]:
            from shared.schemas import ChatMessage

            message = args[0] if args else kwargs.get("message", "")
            session_id = kwargs.get("session_id") or (args[1] if len(args) > 1 else None)
            store = get_session_store()
            if session_id:
                store.append_message(session_id, ChatMessage(role="user", content=message))
            yield StreamChunk(type="content", content="persisted", agent_name=self.name)
            if session_id:
                store.append_message(
                    session_id,
                    ChatMessage(role="assistant", content="persisted"),
                )
            yield StreamChunk(type="done", content="", agent_name=self.name)

    monkeypatch.setattr("server.api.chat.get_general_agent", lambda **_: FakeAgent())

    sid = "sqlite-roundtrip-session"
    with test_client.stream(
        "POST",
        "/v1/chat/stream",
        json={"message": "hello", "session_id": sid},
    ) as resp:
        assert resp.status_code == 200
        resp.read()

    get_resp = test_client.get(f"/v1/sessions/{sid}")
    assert get_resp.status_code == 200
    messages = get_resp.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["content"] == "persisted"

    reset_session_store()
    reset_memory_manager()
    get_settings.cache_clear()


def test_mcp_status_disabled(client: TestClient) -> None:
    resp = client.get("/v1/mcp/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server_enabled"] is False
    assert data["connected"] is False
    names = {s["name"] for s in data["servers"]}
    assert "web_search" in names
    assert "arxiv" in names
    assert "filesystem" in names
    for server in data["servers"]:
        assert server["tools"] == []


@pytest.mark.asyncio
async def test_mcp_status_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ENABLE_MCP", "true")
    monkeypatch.setenv("MCP_ALLOWED_DIRS", str(tmp_path))

    from server.config import get_settings
    from server.mcp.client import _mcp_client, build_mcp_status, reset_mcp_client

    get_settings.cache_clear()
    reset_mcp_client()

    status = await build_mcp_status()
    assert status.server_enabled is True
    assert status.connected is True

    tool_names = {
        tool.qualified_name
        for server in status.servers
        if server.connected
        for tool in server.tools
    }
    assert "arxiv__search_papers" in tool_names
    assert "web_search__search" in tool_names
    assert "filesystem__read_file" in tool_names

    if _mcp_client is not None:
        await _mcp_client.close()
    reset_mcp_client()
    get_settings.cache_clear()

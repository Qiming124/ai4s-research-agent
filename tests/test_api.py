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

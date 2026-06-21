"""Tests for structured logging, token usage store, and stats API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.observability.context import (
    get_agent_name,
    get_request_id,
    get_session_id,
    reset_observability_context,
    set_agent_name,
    set_request_id,
    set_session_id,
)
from server.observability.structured import StructuredLogFormatter, log_event
from server.observability.token_usage import TokenUsageStore, reset_token_usage_store


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    db_path = tmp_path / "sessions.db"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SESSION_DB_PATH", str(db_path))
    monkeypatch.setenv("ENABLE_MCP", "false")
    monkeypatch.setenv("ENABLE_TOKEN_STATS", "true")
    from server.config import get_settings
    from server.mcp.client import reset_mcp_client
    from server.memory.session import reset_session_store

    get_settings.cache_clear()
    reset_mcp_client()
    reset_session_store()
    reset_token_usage_store()
    reset_observability_context()
    yield TestClient(app)
    reset_token_usage_store()
    reset_session_store()
    reset_mcp_client()
    reset_observability_context()
    get_settings.cache_clear()


def test_context_vars() -> None:
    reset_observability_context()
    set_request_id("req-1")
    set_session_id("sess-1")
    set_agent_name("theory")
    assert get_request_id() == "req-1"
    assert get_session_id() == "sess-1"
    assert get_agent_name() == "theory"
    reset_observability_context()
    assert get_request_id() is None


def test_structured_formatter_includes_context() -> None:
    reset_observability_context()
    set_request_id("rid-abc")
    set_session_id("sid-xyz")
    set_agent_name("literature")

    formatter = StructuredLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.structured_fields = {
        "event": "tool_call_complete",
        "tool_name": "arxiv__search",
        "latency_ms": 12.5,
    }
    payload = json.loads(formatter.format(record))
    assert payload["request_id"] == "rid-abc"
    assert payload["session_id"] == "sid-xyz"
    assert payload["agent_name"] == "literature"
    assert payload["event"] == "tool_call_complete"
    assert payload["tool_name"] == "arxiv__search"
    assert payload["latency_ms"] == 12.5


def test_log_event_helper(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("test.observability")
    log_event(
        logger,
        "unit_test_event",
        tool_name="filesystem__read_file",
        latency_ms=3.14,
        status="ok",
    )
    assert any("unit_test_event" in r.getMessage() for r in caplog.records)


def test_token_usage_store_record_and_query(tmp_path: Path) -> None:
    store = TokenUsageStore(tmp_path / "usage.db")
    store.record("s1", "general", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    store.record("s1", "theory", {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28})

    all_stats = store.query()
    assert all_stats["totals"]["event_count"] == 2
    assert all_stats["totals"]["total_tokens"] == 43

    session_stats = store.query(session_id="s1")
    assert session_stats["totals"]["total_tokens"] == 43

    agent_stats = store.query(agent_name="theory")
    assert agent_stats["totals"]["total_tokens"] == 28
    assert agent_stats["by_agent"][0]["agent_name"] == "theory"


def test_stats_api(client: TestClient) -> None:
    from server.observability.token_usage import get_token_usage_store

    store = get_token_usage_store()
    store.record(
        "api-session",
        "literature",
        {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )

    resp = client.get("/v1/stats/tokens", params={"session_id": "api-session"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["totals"]["total_tokens"] == 150
    assert data["filters"]["session_id"] == "api-session"


def test_request_id_header(client: TestClient) -> None:
    resp = client.get("/health", headers={"X-Request-ID": "custom-req-id"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "custom-req-id"

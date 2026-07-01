"""web_search MCP 单元测试。"""

import json
from unittest.mock import patch

import pytest

from server.mcp.servers import web_search as ws


@pytest.mark.asyncio
async def test_search_uses_tavily_when_configured(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    async def fake_tavily(query: str, max_results: int):
        return [{"title": "A", "url": "https://a.test", "snippet": "s"}]

    with patch.object(ws, "_search_tavily", side_effect=fake_tavily):
        out = await ws.search("loss function", 3)
    data = json.loads(out)
    assert data["source"] == "tavily"
    assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_search_returns_setup_hint_without_tavily(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(ws, "_load_tavily_from_env_file", lambda: "")

    async def timeout_coro(*_args, **_kwargs):
        raise TimeoutError

    with (
        patch.object(ws, "_search_tavily", return_value=[]),
        patch.object(ws, "_search_ddg_html", side_effect=timeout_coro),
        patch.object(ws, "_search_ddg_instant", side_effect=timeout_coro),
        patch.object(ws, "_search_wikipedia", side_effect=timeout_coro),
    ):
        out = await ws.search("deep learning", 2)

    data = json.loads(out)
    assert data["results"] == []
    assert "TAVILY_API_KEY" in data.get("setup_hint", "")
    assert any("TAVILY_API_KEY" in err for err in data.get("errors", []))


@pytest.mark.asyncio
async def test_search_skips_ddg_when_tavily_key_configured(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    async def fake_tavily_fail(query: str, max_results: int):
        raise TimeoutError("tavily down")

    async def ddg_should_not_run(*_args, **_kwargs):
        raise AssertionError("duckduckgo should not be called when Tavily key is set")

    with (
        patch.object(ws, "_search_tavily", side_effect=fake_tavily_fail),
        patch.object(ws, "_search_ddg_html", side_effect=ddg_should_not_run),
    ):
        out = await ws.search("SAM", 2)

    data = json.loads(out)
    assert data["results"] == []
    assert "Tavily" in data.get("message", "")


def test_load_tavily_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("TAVILY_API_KEY=tvly-from-file\n", encoding="utf-8")
    monkeypatch.setattr(ws, "_project_root", lambda: tmp_path)
    assert ws._tavily_api_key() == "tvly-from-file"


def test_build_multiserver_connections_omits_empty_env():
    from server.mcp.config import MCPServerConfig, build_multiserver_connections

    configs = {
        "web_search": MCPServerConfig(
            command="python",
            args=["-m", "server.mcp.servers.web_search"],
            env={"TAVILY_API_KEY": ""},
            enabled=True,
        )
    }
    conns = build_multiserver_connections(configs)
    assert "env" not in conns["web_search"]

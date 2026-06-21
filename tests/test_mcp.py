"""
MCP Client 与 Registry 测试。
"""

from __future__ import annotations

import sys

import pytest

from server.langchain.mcp import build_multiserver_connections
from server.mcp.config import MCPServerConfig
from server.mcp.registry import ToolRegistry


def test_build_multiserver_connections_stdio() -> None:
    configs = {
        "filesystem": MCPServerConfig(
            command="python",
            args=["-m", "server.mcp.servers.filesystem"],
            env={"MCP_ALLOWED_DIRS": "/tmp"},
            enabled=True,
        ),
        "disabled": MCPServerConfig(command="echo", args=[], enabled=False),
    }
    connections = build_multiserver_connections(configs)
    assert set(connections) == {"filesystem"}
    fs = connections["filesystem"]
    assert fs["transport"] == "stdio"
    assert fs["command"] == sys.executable
    assert fs["args"] == ["-m", "server.mcp.servers.filesystem"]
    assert fs["env"] == {"MCP_ALLOWED_DIRS": "/tmp"}


def test_tool_registry_openai_format() -> None:
    registry = ToolRegistry()
    registry.register(
        server_name="arxiv",
        tool_name="search_papers",
        description="Search arXiv",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    tools = registry.to_openai_tools()
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "arxiv__search_papers"
    assert "query" in tools[0]["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_mcp_client_connects_builtin_servers(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("MCP_ALLOWED_DIRS", str(tmp_path))
    from server.config import get_settings

    get_settings.cache_clear()

    from server.mcp.client import MCPClient, reset_mcp_client

    reset_mcp_client()
    settings = get_settings()
    settings = settings.model_copy(update={"enable_mcp": True})
    client = MCPClient(settings)
    await client.connect()

    assert client.is_connected
    tools = client.get_openai_tools()
    names = {t["function"]["name"] for t in tools}
    assert "arxiv__search_papers" in names
    assert "web_search__search" in names
    assert "filesystem__read_file" in names

    result = await client.call_tool(
        "filesystem__write_file",
        {"path": "test.txt", "content": "hello mcp"},
    )
    assert "hello mcp" in result or "已写入" in result

    read_back = await client.call_tool(
        "filesystem__read_file",
        {"path": "test.txt"},
    )
    assert read_back == "hello mcp"

    await client.close()
    reset_mcp_client()
    get_settings.cache_clear()

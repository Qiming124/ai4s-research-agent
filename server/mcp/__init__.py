# MCP 工具层（Phase 2B）：Client + Registry + 自研 Server。
# Client 延迟导入，避免 MCP stdio 子进程加载 server.mcp.servers.* 时触发 LangChain 循环依赖。

from __future__ import annotations

from typing import TYPE_CHECKING

from server.mcp.registry import ToolRegistry

if TYPE_CHECKING:
    from server.mcp.client import MCPClient

__all__ = ["MCPClient", "ToolRegistry", "get_mcp_client", "reset_mcp_client"]


def __getattr__(name: str):
    if name in __all__ and name != "ToolRegistry":
        from server.mcp.client import MCPClient, get_mcp_client, reset_mcp_client

        return {
            "MCPClient": MCPClient,
            "get_mcp_client": get_mcp_client,
            "reset_mcp_client": reset_mcp_client,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

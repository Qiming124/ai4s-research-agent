# =============================================================================
# MCP 工具层（Phase 2B）。
#
# 架构：
#     MCPClient      — 连接管理 + 工具调用 + 全局单例
#     ToolRegistry   — 工具命名空间 {qualified_name → tool}
#     mcp/config.py  — mcp_servers.json 加载与解析
#     mcp/whitelist.py — 工具白名单 glob 过滤
#     mcp/truncation.py — 工具结果截断
#     mcp/servers/   — 自研 MCP Server（arxiv / web_search / filesystem）
#
# 延迟导入：
#     MCPClient 使用 TYPE_CHECKING + 模块级 __getattr__ 延迟导入，
#     避免 MCP stdio 子进程在加载 server.mcp.servers.* 时触发 LangChain 循环依赖。
#
# 使用：
#     from server.mcp import get_mcp_client
#     client = await get_mcp_client()
#     result = await client.call_tool("web_search__search", {"query": "..."})
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING

# ToolRegistry 无外部循环依赖，可立即导入
from server.mcp.registry import ToolRegistry

# MCPClient / get_mcp_client / reset_mcp_client 延迟导入
if TYPE_CHECKING:
    from server.mcp.client import MCPClient

__all__ = ["MCPClient", "ToolRegistry", "get_mcp_client", "reset_mcp_client"]


def __getattr__(name: str):
    """
    模块级 __getattr__：首次访问 MCPClient / get_mcp_client / reset_mcp_client 时才 import。

    这种模式解决了两层依赖问题：
        server.mcp.servers.* 在自己的 __main__ 块中用 mcp.run(transport="stdio")
        若 server.mcp.__init__ 在模块加载时直接 import client，
        会导致 LangChain 初始化流程在 stdio server 子进程中触发，引发循环引用。

    延迟到运行时首次调用 get_mcp_client 才加载 client 模块。
    """
    if name in __all__ and name != "ToolRegistry":
        from server.mcp.client import MCPClient, get_mcp_client, reset_mcp_client

        return {
            "MCPClient": MCPClient,
            "get_mcp_client": get_mcp_client,
            "reset_mcp_client": reset_mcp_client,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

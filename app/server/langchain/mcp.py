"""
LangChain MCP bridge — 从 server.mcp.config 重新导出。

职责：为 LangGraph 路径提供与 Legacy 路径一致的 MCP 连接配置。
"""

from server.mcp.config import build_multiserver_connections, create_multiserver_client

__all__ = ["build_multiserver_connections", "create_multiserver_client"]

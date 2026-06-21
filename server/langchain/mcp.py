# Re-export MCP config bridge for the LangChain adapter layer.

from server.mcp.config import build_multiserver_connections, create_multiserver_client

__all__ = ["build_multiserver_connections", "create_multiserver_client"]

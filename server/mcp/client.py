# MCP Client：通过 langchain-mcp-adapters MultiServerMCPClient 连接多个 stdio MCP Server。

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp import ClientSession

from server.config import Settings, get_settings
from server.langchain.mcp import create_multiserver_client
from server.mcp.config import load_mcp_servers
from server.mcp.registry import ToolRegistry

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._registry = ToolRegistry()
        self._adapter: MultiServerMCPClient | None = None
        self._sessions: dict[str, ClientSession] = {}
        self._exit_stack: AsyncExitStack | None = None
        self._connected = False

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if self._connected:
            return

        configs = load_mcp_servers(self._settings.mcp_config_path)
        if not configs:
            logger.warning("MCP 配置文件为空或不存在: %s", self._settings.mcp_config_path)
            return

        self._adapter = create_multiserver_client(configs)
        if not self._adapter.connections:
            logger.warning("MCP 无已启用的 Server 配置")
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        for server_name in self._adapter.connections:
            try:
                await self._connect_server(server_name)
            except Exception:
                logger.exception("连接 MCP Server 失败: %s", server_name)

        self._connected = True
        logger.info(
            "MCP Client 已连接 %d 个 Server，共 %d 个工具",
            len(self._sessions),
            len(self._registry.tools),
        )

    async def _connect_server(self, server_name: str) -> None:
        assert self._adapter is not None
        assert self._exit_stack is not None

        session = await self._exit_stack.enter_async_context(
            self._adapter.session(server_name)
        )
        self._sessions[server_name] = session

        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            self._registry.register(
                server_name=server_name,
                tool_name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {"type": "object", "properties": {}},
            )
        logger.info("MCP Server [%s] 注册 %d 个工具", server_name, len(tools_result.tools))

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> str:
        registered = self._registry.get(qualified_name)
        if registered is None:
            raise ValueError(f"未知工具: {qualified_name}")

        session = self._sessions.get(registered.server_name)
        if session is None:
            raise RuntimeError(f"MCP Server 未连接: {registered.server_name}")

        result = await session.call_tool(registered.tool_name, arguments)
        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts) if parts else str(result.content)

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._adapter = None
        self._sessions.clear()
        self._registry.clear()
        self._connected = False

    def is_server_connected(self, server_name: str) -> bool:
        return server_name in self._sessions

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return self._registry.to_openai_tools()


_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
        if get_settings().enable_mcp:
            await _mcp_client.connect()
    return _mcp_client


def reset_mcp_client() -> None:
    global _mcp_client
    _mcp_client = None


async def build_mcp_status() -> "MCPStatusResponse":
    from shared.schemas import MCPServerInfo, MCPStatusResponse, MCPToolInfo

    settings = get_settings()
    configs = load_mcp_servers(settings.mcp_config_path)

    client: MCPClient | None = None
    connected = False
    if settings.enable_mcp:
        client = await get_mcp_client()
        connected = client.is_connected

    tools_by_server: dict[str, list[MCPToolInfo]] = {}
    if client is not None and connected:
        for reg in client.registry.list_tools():
            tools_by_server.setdefault(reg.server_name, []).append(
                MCPToolInfo(
                    qualified_name=reg.qualified_name,
                    tool_name=reg.tool_name,
                    description=reg.description,
                )
            )

    servers: list[MCPServerInfo] = []
    for name, cfg in configs.items():
        is_connected = client is not None and client.is_server_connected(name)
        servers.append(
            MCPServerInfo(
                name=name,
                enabled=cfg.enabled,
                connected=is_connected,
                tools=tools_by_server.get(name, []),
            )
        )

    return MCPStatusResponse(
        server_enabled=settings.enable_mcp,
        connected=connected,
        servers=servers,
    )

# MCP Client：通过 langchain-mcp-adapters MultiServerMCPClient 连接多个 stdio MCP Server。

from __future__ import annotations

import logging
import time
from contextlib import AsyncExitStack
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp import ClientSession

from server.config import Settings, get_settings
from server.langchain.mcp import create_multiserver_client
from server.mcp.config import load_mcp_servers, sync_mcp_runtime_env
from server.mcp.registry import ToolRegistry
from server.mcp.whitelist import filter_openai_tools
from server.observability.structured import log_event

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 多 Server 客户端：通过 stdio 连接 mcp_servers.json 中配置的 Server。

    属性:
        registry: 已注册工具的 ToolRegistry
        is_connected: 是否已完成 connect
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        初始化客户端（不自动连接，需调用 connect）。

        参数:
            settings: 可选 Settings，默认 get_settings()
        """
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
        """
        按配置连接所有已启用的 MCP Server 并注册工具。

        返回:
            无；连接失败的分 Server 记录日志但不中断其他 Server
        """
        if self._connected:
            return

        sync_mcp_runtime_env(self._settings)
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

        start = time.perf_counter()
        try:
            if qualified_name == "rag__retrieve":
                from server.memory.rag.context import get_rag_session_id

                sid = get_rag_session_id()
                if sid and not arguments.get("session_id"):
                    arguments = {**arguments, "session_id": sid}
            result = await session.call_tool(registered.tool_name, arguments)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            log_event(
                logger,
                "tool_call_error",
                level=logging.ERROR,
                tool_name=qualified_name,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            logger,
            "tool_call_complete",
            tool_name=qualified_name,
            latency_ms=latency_ms,
        )

        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts) if parts else str(result.content)

    async def close(self) -> None:
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except RuntimeError as exc:
                # stdio MCP sessions bind AsyncExitStack to the connect task;
                # reload from a different request task cannot aclose cleanly.
                logger.warning("MCP exit stack close skipped (cross-task): %s", exc)
            self._exit_stack = None
        self._adapter = None
        self._sessions.clear()
        self._registry.clear()
        self._connected = False

    def is_server_connected(self, server_name: str) -> bool:
        return server_name in self._sessions

    def get_openai_tools(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        tools = self._registry.to_openai_tools()
        return filter_openai_tools(tools, self._settings, agent_name)


_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    """
    获取全局 MCPClient 单例；首次调用且 ENABLE_MCP 为 true 时执行 connect。

    返回:
        MCPClient 实例
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
        if get_settings().enable_mcp:
            await _mcp_client.connect()
    return _mcp_client


def reset_mcp_client() -> None:
    global _mcp_client
    _mcp_client = None


async def reload_mcp_client() -> MCPClient:
    """断开并重新加载 MCP 配置（热重载）。"""
    global _mcp_client
    sync_mcp_runtime_env(get_settings())
    if _mcp_client is not None:
        await _mcp_client.close()
    _mcp_client = None
    return await get_mcp_client()


async def build_mcp_status() -> "MCPStatusResponse":
    """
    构建 GET /v1/mcp/status 的响应体。

    返回:
        MCPStatusResponse，含 server_enabled、connected、各 Server 工具列表
    """

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

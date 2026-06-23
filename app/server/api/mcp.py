# MCP 状态 API：返回服务端 ENABLE_MCP、连接状态与各 Server 工具列表。

from __future__ import annotations

from fastapi import APIRouter

from server.mcp.client import build_mcp_status
from shared.schemas import MCPStatusResponse

router = APIRouter(tags=["mcp"])


@router.get("/v1/mcp/status", response_model=MCPStatusResponse)
async def mcp_status() -> MCPStatusResponse:
    """
    查询 MCP 启用状态、Client 连接与各 Server 工具列表。

    返回:
        MCPStatusResponse: server_enabled、connected、servers
    """
    return await build_mcp_status()

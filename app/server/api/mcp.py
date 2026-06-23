# MCP 状态 API：返回服务端 ENABLE_MCP、连接状态与各 Server 工具列表。

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.config import get_settings
from server.mcp.client import build_mcp_status, reload_mcp_client
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


@router.post("/v1/mcp/reload", response_model=MCPStatusResponse)
async def mcp_reload() -> MCPStatusResponse:
    """重新加载 mcp_servers.json 并重建 MCP 连接（无需重启 uvicorn）。"""
    settings = get_settings()
    if not settings.enable_mcp:
        raise HTTPException(status_code=400, detail="MCP 未启用（ENABLE_MCP=false）")
    await reload_mcp_client()
    return await build_mcp_status()

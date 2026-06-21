# MCP 状态 API。

from __future__ import annotations

from fastapi import APIRouter

from server.mcp.client import build_mcp_status
from shared.schemas import MCPStatusResponse

router = APIRouter(tags=["mcp"])


@router.get("/v1/mcp/status", response_model=MCPStatusResponse)
async def mcp_status() -> MCPStatusResponse:
    return await build_mcp_status()

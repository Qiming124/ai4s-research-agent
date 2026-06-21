"""Token usage statistics API (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from server.observability.token_usage import get_token_usage_store
from shared.schemas import TokenUsageStatsResponse

router = APIRouter(tags=["stats"])


@router.get("/v1/stats/tokens", response_model=TokenUsageStatsResponse)
async def get_token_stats(
    session_id: str | None = Query(default=None, description="按会话 ID 过滤"),
    agent_name: str | None = Query(default=None, description="按 Agent 名称过滤"),
    day: str | None = Query(default=None, description="按日期过滤 (YYYY-MM-DD)"),
) -> TokenUsageStatsResponse:
    data = get_token_usage_store().query(
        session_id=session_id,
        agent_name=agent_name,
        day=day,
    )
    return TokenUsageStatsResponse.model_validate(data)

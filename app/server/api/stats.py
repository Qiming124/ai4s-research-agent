# Token 用量统计 API（Phase 6）。

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
    """
    聚合查询 SQLite 中的 LLM token 用量。

    参数:
        session_id: 可选，按会话过滤
        agent_name: 可选，按 Agent 过滤
        day: 可选，按日期 YYYY-MM-DD 过滤

    返回:
        TokenUsageStatsResponse: totals 与 by_agent 明细
    """
    data = get_token_usage_store().query(
        session_id=session_id,
        agent_name=agent_name,
        day=day,
    )
    return TokenUsageStatsResponse.model_validate(data)

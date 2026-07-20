# =============================================================================
# Token 用量统计 HTTP API（Phase 6）。
#
# 职责：
#     1. 暴露 GET /v1/stats/tokens 聚合查询端点
#     2. 按 session_id / agent_name / day 过滤 SQLite 事件表
#     3. 返回 prompt / completion / total tokens 汇总
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/observability/token_usage.py
#
# 阅读提示：
#     - 新人先看 get_token_stats 与 token_usage.query()
#
# Debug：
#     - 统计为空 → chat turn 未调用 record() 或 SESSION_STORE_BACKEND 切换
#     - 日期过滤无效 → day 格式须 YYYY-MM-DD
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Query

from server.observability.token_usage import get_token_usage_store
from shared.schemas import TokenUsageStatsResponse

router = APIRouter(tags=["stats"])


@router.get("/v1/stats/tokens", response_model=TokenUsageStatsResponse, summary="Token 用量统计")
async def get_token_stats(
    session_id: str | None = Query(default=None, description="按会话 ID 过滤", examples=["sess_demo"]),
    agent_name: str | None = Query(default=None, description="按 Agent 名称过滤", examples=["theory"]),
    day: str | None = Query(default=None, description="按日期过滤 (YYYY-MM-DD)", examples=["2026-07-20"]),
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

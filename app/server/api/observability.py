# =============================================================================
# 可观测性与质量面板 HTTP API。
#
# 职责：
#     1. 聚合验证通过率、按 Agent 分桶统计
#     2. 暴露 observability_summary 与 agent_quality 端点
#     3. 为前端质量仪表盘提供数据源
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/verification.py（验证账本）
#
# 阅读提示：
#     - 新人先看 observability_summary
#
# Debug：
#     - 通过率恒为 0 → project_id 过滤与记录 project 字段不匹配
#     - 数据偏少 → list_records limit 默认 500
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter

from server.memory.verification import get_verification_ledger
from shared.schemas import AgentQualityResponse, ObservabilitySummary

router = APIRouter(tags=["observability"])


@router.get("/v1/observability/summary", response_model=ObservabilitySummary)
async def observability_summary(project_id: str = "default") -> ObservabilitySummary:
    ledger = get_verification_ledger()
    records = ledger.list_records(project_id=project_id, limit=500)
    total = len(records)
    passed = sum(1 for r in records if r["passed"])
    rate = (passed / total * 100) if total else 0.0
    by_agent: dict[str, dict[str, int]] = {}
    for r in records:
        agent = r.get("agent_name", "unknown")
        bucket = by_agent.setdefault(agent, {"total": 0, "passed": 0})
        bucket["total"] += 1
        if r["passed"]:
            bucket["passed"] += 1
    return ObservabilitySummary(
        project_id=project_id,
        verification_total=total,
        verification_passed=passed,
        verification_pass_rate=round(rate, 2),
        by_agent=by_agent,
    )


@router.get("/v1/observability/agent-quality", response_model=AgentQualityResponse)
async def agent_quality(project_id: str = "default") -> AgentQualityResponse:
    ledger = get_verification_ledger()
    records = ledger.list_records(project_id=project_id, limit=500)
    agents: dict[str, dict[str, float | int]] = {}
    for r in records:
        name = r.get("agent_name", "unknown")
        a = agents.setdefault(name, {"runs": 0, "passed": 0})
        a["runs"] = int(a["runs"]) + 1
        if r["passed"]:
            a["passed"] = int(a["passed"]) + 1
    breakdown = []
    for name, stats in agents.items():
        runs = int(stats["runs"])
        passed = int(stats["passed"])
        breakdown.append(
            {
                "agent_name": name,
                "runs": runs,
                "passed": passed,
                "pass_rate": round(passed / runs * 100, 2) if runs else 0.0,
            }
        )
    return AgentQualityResponse(agents=breakdown)

# =============================================================================
# 验证账本 HTTP API。
#
# 职责：
#     1. 列出 SymPy / 数值验证记录（按 project / session / entry 过滤）
#     2. 触发单条 Claim 验证（execute_claim_verification）
#     3. 提供验证仪表盘聚合数据
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/experiments/verification_executor.py、memory/verification.py
#
# 阅读提示：
#     - 新人先看 list_verification_records 与 run_verification
#
# Debug：
#     - 仪表盘为空 → project_id 与 session 所属课题不一致
#     - 验证失败 → MCP numerical/sympy 未连接或 claim 无法解析
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter

from server.experiments.verification_executor import execute_claim_verification
from server.memory.verification import get_verification_ledger
from shared.schemas import (
    VerificationClaimRequest,
    VerificationDashboardResponse,
    VerificationRecordInfo,
    VerificationRecordsResponse,
)

router = APIRouter(tags=["verification"])


@router.get("/v1/verification/records", response_model=VerificationRecordsResponse)
async def list_verification_records(
    project_id: str | None = None,
    session_id: str | None = None,
    entry_id: int | None = None,
    limit: int = 100,
) -> VerificationRecordsResponse:
    ledger = get_verification_ledger()
    records = ledger.list_records(
        project_id=project_id,
        session_id=session_id,
        entry_id=entry_id,
        limit=limit,
    )
    return VerificationRecordsResponse(
        records=[VerificationRecordInfo(**r) for r in records],
        total=len(records),
    )


@router.get("/v1/verification/dashboard", response_model=VerificationDashboardResponse)
async def verification_dashboard(
    project_id: str = "default",
    session_id: str | None = None,
) -> VerificationDashboardResponse:
    ledger = get_verification_ledger()
    records = ledger.list_records(project_id=project_id, session_id=session_id, limit=200)
    by_tier: dict[str, int] = {"symbolic": 0, "numerical": 0, "experiment": 0}
    passed = 0
    failed = 0
    for r in records:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
        if r["passed"]:
            passed += 1
        else:
            failed += 1
    return VerificationDashboardResponse(
        project_id=project_id,
        total_records=len(records),
        passed=passed,
        failed=failed,
        by_tier=by_tier,
        recent=[VerificationRecordInfo(**r) for r in records[:20]],
    )


@router.post("/v1/verification/run")
async def run_verification(request: VerificationClaimRequest) -> dict:
    project_id = request.project_id or "default"
    # 有会话时以会话所属课题为准，避免写入 default 导致仪表盘按课题查询为空
    if request.session_id:
        from server.memory.projects import get_project_store

        linked = get_project_store().get_project_for_session(request.session_id)
        if linked:
            project_id = linked
    result = await execute_claim_verification(
        request.claim,
        session_id=request.session_id,
        project_id=project_id,
        entry_id=request.entry_id,
        agent_name="api",
        persist=request.persist,
    )
    return result

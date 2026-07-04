# 验证账本 API。

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
    result = await execute_claim_verification(
        request.claim,
        session_id=request.session_id,
        project_id=request.project_id,
        entry_id=request.entry_id,
        agent_name="api",
    )
    return result

# =============================================================================
# 课题审计日志 HTTP API。
#
# 职责：列出课题操作审计（会话关联等本地流水）。
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from server.memory.projects import get_project_store

router = APIRouter(tags=["sync"])


@router.get("/v1/sync/audit/{project_id}", summary="课题审计日志")
async def list_sync_audit(
    project_id: str = Path(..., description="课题 ID", examples=["default"]),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="返回条数上限",
        examples=[50],
    ),
) -> dict:
    """列出课题审计日志（如 link_session / unlink_session）。"""
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    return {"audit": store.list_audit(project_id, limit=limit)}

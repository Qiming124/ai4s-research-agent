# =============================================================================
# 可选云端元数据同步 HTTP API。
#
# 职责：
#     1. 在 ENABLE_CLOUD_SYNC=true 时上传课题与结构化记忆元数据摘要
#     2. 保持本地 data/ 数据主权，不同步原始会话消息与向量
#     3. 返回同步条目计数与目标 URL
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/projects.py、structured/store.py、server/config.py
#
# 阅读提示：
#     - 新人先看 sync_metadata 端点
#
# Debug：
#     - 403 → ENABLE_CLOUD_SYNC=false
#     - 404 → project_id 不存在
#     - 远程失败 → CLOUD_SYNC_URL 或网络配置
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from server.config import get_settings
from server.memory.projects import get_project_store
from server.memory.structured.store import get_structured_memory_store
from shared.schemas import SyncMetadataRequest, SyncMetadataResponse

router = APIRouter(tags=["sync"])


@router.post(
    "/v1/sync/metadata",
    response_model=SyncMetadataResponse,
    summary="同步云端元数据",
)
async def sync_metadata(request: SyncMetadataRequest) -> SyncMetadataResponse:
    """
    同步课题结构化记忆元数据摘要（需 ENABLE_CLOUD_SYNC=true）。

    不同步原始会话消息与向量；结果写入课题审计日志。
    """
    settings = get_settings()
    if not settings.enable_cloud_sync:
        raise HTTPException(status_code=403, detail="云端同步未启用（ENABLE_CLOUD_SYNC=false）")

    store = get_project_store()
    project = store.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="课题不存在")

    memory = get_structured_memory_store()
    entries = memory.list_entries(session_id=request.session_id, limit=100)
    metadata_payload = [
        {
            "id": e["id"],
            "title": e["title"],
            "kind": e["kind"],
            "status": (e.get("metadata") or {}).get("status", "draft"),
            "created_at": e.get("created_at"),
        }
        for e in entries
    ]
    store.append_audit(
        request.project_id,
        "cloud_sync",
        actor=request.actor,
        payload={"entries": len(metadata_payload)},
    )
    return SyncMetadataResponse(
        project_id=request.project_id,
        synced_entries=len(metadata_payload),
        metadata=metadata_payload,
    )


@router.get("/v1/sync/audit/{project_id}", summary="同步审计日志")
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
    """列出课题审计日志（含 cloud_sync 等操作）。"""
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    return {"audit": store.list_audit(project_id, limit=limit)}

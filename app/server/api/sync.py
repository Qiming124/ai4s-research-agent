# 可选云端元数据同步（本地数据主权，仅同步元数据）。

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.config import get_settings
from server.memory.projects import get_project_store
from server.memory.structured.store import get_structured_memory_store
from shared.schemas import SyncMetadataRequest, SyncMetadataResponse

router = APIRouter(tags=["sync"])


@router.post("/v1/sync/metadata", response_model=SyncMetadataResponse)
async def sync_metadata(request: SyncMetadataRequest) -> SyncMetadataResponse:
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


@router.get("/v1/sync/audit/{project_id}")
async def list_sync_audit(project_id: str, limit: int = 50) -> dict:
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    return {"audit": store.list_audit(project_id, limit=limit)}

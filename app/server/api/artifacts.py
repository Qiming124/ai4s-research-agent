# =============================================================================
# Artifact HTTP API：列表 / 详情 / 手动创建。
# =============================================================================

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.artifacts.store import get_artifact_store
from shared.artifact_models import (
    ArtifactDetailResponse,
    ArtifactListResponse,
    ArtifactType,
)

router = APIRouter(tags=["artifacts"])


class ArtifactCreateRequest(BaseModel):
    type: ArtifactType
    data: dict[str, Any] = Field(default_factory=dict)
    project_id: str = "default"
    session_id: str | None = None


class ArtifactUpdateRequest(BaseModel):
    project_id: str = "default"
    data: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/artifacts", response_model=ArtifactListResponse, summary="列出课题工件")
async def list_artifacts(
    project_id: str = Query(default="default", description="课题 ID"),
    session_id: str | None = Query(default=None, description="按会话过滤"),
    types: str | None = Query(
        default=None,
        description="逗号分隔类型，如 MethodCard,ExperimentPlan",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> ArtifactListResponse:
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    store = get_artifact_store()
    items = store.list(project_id, types=type_list, session_id=session_id, limit=limit)
    return ArtifactListResponse(artifacts=items)


@router.get(
    "/v1/artifacts/{artifact_id}",
    response_model=ArtifactDetailResponse,
    summary="获取工件详情",
)
async def get_artifact(
    artifact_id: str,
    project_id: str = Query(default="default"),
) -> ArtifactDetailResponse:
    store = get_artifact_store()
    found = store.get_by_id(project_id, artifact_id)
    if not found:
        raise HTTPException(status_code=404, detail="工件不存在")
    artifact_type, data = found
    return ArtifactDetailResponse(type=artifact_type, data=data)


@router.post("/v1/artifacts", response_model=ArtifactDetailResponse, summary="手动创建工件")
async def create_artifact(request: ArtifactCreateRequest) -> ArtifactDetailResponse:
    store = get_artifact_store()
    payload = {**request.data, "project_id": request.project_id}
    if request.session_id:
        payload["session_id"] = request.session_id
    saved = store.save(request.type, payload)
    return ArtifactDetailResponse(type=request.type, data=saved)


@router.patch(
    "/v1/artifacts/{artifact_id}",
    response_model=ArtifactDetailResponse,
    summary="更新工件",
)
async def update_artifact(
    artifact_id: str,
    request: ArtifactUpdateRequest,
) -> ArtifactDetailResponse:
    if not request.data:
        raise HTTPException(status_code=400, detail="data 不能为空")
    store = get_artifact_store()
    updated = store.update(request.project_id, artifact_id, request.data)
    if not updated:
        raise HTTPException(status_code=404, detail="工件不存在")
    artifact_type, data = updated
    return ArtifactDetailResponse(type=artifact_type, data=data)


@router.delete("/v1/artifacts/{artifact_id}", summary="删除工件")
async def delete_artifact(
    artifact_id: str,
    project_id: str = Query(default="default"),
) -> dict[str, Any]:
    store = get_artifact_store()
    ok = store.delete(project_id, artifact_id)
    if not ok:
        raise HTTPException(status_code=404, detail="工件不存在")
    return {"ok": True, "id": artifact_id}

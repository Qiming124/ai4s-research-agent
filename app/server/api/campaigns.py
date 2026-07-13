# 科研 Campaign API。

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.memory.campaigns import get_campaign_store
from server.memory.projects import get_project_store
from shared.schemas import (
    ResearchCampaignCreateRequest,
    ResearchCampaignInfo,
    ResearchCampaignListResponse,
    ResearchCampaignUpdateRequest,
)

router = APIRouter(tags=["campaigns"])


def _require_project(project_id: str) -> str:
    store = get_project_store()
    resolved = store.resolve_project_id(project_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="课题不存在")
    return resolved


@router.get(
    "/v1/projects/{project_id}/campaign",
    response_model=ResearchCampaignInfo,
)
async def get_active_campaign(project_id: str) -> ResearchCampaignInfo:
    pid = _require_project(project_id)
    camp = get_campaign_store().get_active_campaign(pid)
    if not camp:
        raise HTTPException(status_code=404, detail="无活跃 Campaign")
    return ResearchCampaignInfo(**camp)


@router.get(
    "/v1/projects/{project_id}/campaigns",
    response_model=ResearchCampaignListResponse,
)
async def list_campaigns(project_id: str) -> ResearchCampaignListResponse:
    pid = _require_project(project_id)
    campaigns = [
        ResearchCampaignInfo(**c) for c in get_campaign_store().list_campaigns(pid)
    ]
    return ResearchCampaignListResponse(campaigns=campaigns, total=len(campaigns))


@router.post(
    "/v1/projects/{project_id}/campaign",
    response_model=ResearchCampaignInfo,
)
async def create_campaign(
    project_id: str,
    request: ResearchCampaignCreateRequest,
) -> ResearchCampaignInfo:
    pid = _require_project(project_id)
    camp = get_campaign_store().create_campaign(
        pid,
        title=request.title,
        task_family=request.task_family,
        dataset=request.dataset,
        benchmark=request.benchmark,
        sota_reference=request.sota_reference,
        compute_budget=request.compute_budget,
        assumptions=request.assumptions,
        session_id=request.session_id,
    )
    get_project_store().append_audit(
        pid,
        "create_campaign",
        payload={"campaign_id": camp["id"], "title": camp["title"]},
    )
    return ResearchCampaignInfo(**camp)


@router.get(
    "/v1/projects/{project_id}/campaigns/{campaign_id}",
    response_model=ResearchCampaignInfo,
)
async def get_campaign(project_id: str, campaign_id: str) -> ResearchCampaignInfo:
    pid = _require_project(project_id)
    camp = get_campaign_store().get_campaign(campaign_id)
    if not camp or camp["project_id"] != pid:
        raise HTTPException(status_code=404, detail="Campaign 不存在")
    return ResearchCampaignInfo(**camp)


@router.patch(
    "/v1/projects/{project_id}/campaigns/{campaign_id}",
    response_model=ResearchCampaignInfo,
)
async def update_campaign(
    project_id: str,
    campaign_id: str,
    request: ResearchCampaignUpdateRequest,
) -> ResearchCampaignInfo:
    pid = _require_project(project_id)
    camp = get_campaign_store().get_campaign(campaign_id)
    if not camp or camp["project_id"] != pid:
        raise HTTPException(status_code=404, detail="Campaign 不存在")
    updated = get_campaign_store().update_campaign(
        campaign_id,
        current_stage=request.current_stage,
        status=request.status,
        stage_artifacts=request.stage_artifacts,
        gates=request.gates,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Campaign 更新失败")
    return ResearchCampaignInfo(**updated)

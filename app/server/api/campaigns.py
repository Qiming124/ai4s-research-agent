# =============================================================================
# 科研 Campaign HTTP API。
#
# 职责：
#     1. 创建、查询、更新、列出课题下的 Research Campaign
#     2. 校验 project_id 存在性
#     3. 暴露 Campaign 阶段、门禁与产物元数据
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/campaigns.py、projects.py
#
# 阅读提示：
#     - 新人先看 create_campaign 与 get_campaign
#     - 阶段常量 CAMPAIGN_STAGES 在 memory/campaigns.py
#
# Debug：
#     - 404 → _require_project 未解析到课题
#     - Campaign 卡住 → 查 gates 字段与 research_supervisor 日志
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

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
    summary="当前活跃 Campaign",
)
async def get_active_campaign(
    project_id: str = Path(..., description="课题 ID", examples=["default"]),
) -> ResearchCampaignInfo:
    """
    返回课题下用于展示的 Campaign（优先最近更新，含已完成）。

    异常:
        404: 课题不存在，或尚无 Campaign
    """
    pid = _require_project(project_id)
    # 展示用：优先最近更新（含已完成），避免被更旧的未结束演示 Campaign 盖住进度
    camp = get_campaign_store().get_active_campaign(pid, prefer_open=False)
    if not camp:
        raise HTTPException(status_code=404, detail="无活跃 Campaign")
    return ResearchCampaignInfo(**camp)


@router.get(
    "/v1/projects/{project_id}/campaigns",
    response_model=ResearchCampaignListResponse,
    summary="Campaign 列表",
)
async def list_campaigns(
    project_id: str = Path(..., description="课题 ID", examples=["default"]),
) -> ResearchCampaignListResponse:
    """列出课题下全部 Research Campaign。"""
    pid = _require_project(project_id)
    campaigns = [
        ResearchCampaignInfo(**c) for c in get_campaign_store().list_campaigns(pid)
    ]
    return ResearchCampaignListResponse(campaigns=campaigns, total=len(campaigns))


@router.post(
    "/v1/projects/{project_id}/campaign",
    response_model=ResearchCampaignInfo,
    summary="创建并启动 Campaign",
)
async def create_campaign(
    request: ResearchCampaignCreateRequest,
    project_id: str = Path(..., description="课题 ID", examples=["default"]),
) -> ResearchCampaignInfo:
    """
    创建科研 Campaign（默认阶段 S0_campaign，状态 active），并写入课题审计日志。
    """
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
    summary="Campaign 详情",
)
async def get_campaign(
    project_id: str = Path(..., description="课题 ID", examples=["default"]),
    campaign_id: str = Path(..., description="Campaign ID", examples=["camp_demo"]),
) -> ResearchCampaignInfo:
    """按 ID 查询 Campaign；须属于指定课题。"""
    pid = _require_project(project_id)
    camp = get_campaign_store().get_campaign(campaign_id)
    if not camp or camp["project_id"] != pid:
        raise HTTPException(status_code=404, detail="Campaign 不存在")
    return ResearchCampaignInfo(**camp)


@router.patch(
    "/v1/projects/{project_id}/campaigns/{campaign_id}",
    response_model=ResearchCampaignInfo,
    summary="更新 Campaign 阶段/状态",
)
async def update_campaign(
    request: ResearchCampaignUpdateRequest,
    project_id: str = Path(..., description="课题 ID", examples=["default"]),
    campaign_id: str = Path(..., description="Campaign ID", examples=["camp_demo"]),
) -> ResearchCampaignInfo:
    """
    更新 current_stage、status、stage_artifacts、gates（仅传入的字段生效）。
    """
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

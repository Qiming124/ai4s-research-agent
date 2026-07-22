# 提示词优化 API：模板列表、测试案例、AI 多风格对比择优。
#
# 内置文案来自 conf/prompt/*.json（非硬编码长字符串）；
# 前端仅需 GET 列表；单条详情已移除（列表已含全文）。

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.llm.prompt_optimizer import optimize_user_prompt
from server.llm.prompt_templates import list_templates
from server.llm.prompt_test_cases import list_test_cases
from shared.schemas import (
    PromptOptimizeRequest,
    PromptOptimizeResponse,
    PromptStyleVariant,
    PromptTemplateInfo,
    PromptTestCaseInfo,
)

router = APIRouter(tags=["prompt"])


@router.get("/v1/prompt/templates", response_model=list[PromptTemplateInfo])
async def prompt_templates() -> list[PromptTemplateInfo]:
    """返回支持的科研提示词风格模板（conf/prompt/templates.json）。"""
    return [PromptTemplateInfo(**t) for t in list_templates()]


@router.get("/v1/prompt/test-cases", response_model=list[PromptTestCaseInfo])
async def prompt_test_cases() -> list[PromptTestCaseInfo]:
    """返回科研场景测试案例（conf/prompt/test_cases.json）。"""
    return [PromptTestCaseInfo(**c) for c in list_test_cases()]


@router.post("/v1/prompt/optimize", response_model=PromptOptimizeResponse)
async def prompt_optimize(request: PromptOptimizeRequest) -> PromptOptimizeResponse:
    """AI 生成多风格优化提示词，打分对比并推荐最优。"""
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    try:
        result = await optimize_user_prompt(
            text=text,
            context=request.context or "",
            goal=request.goal or "",
            mode=request.mode or "chat",
            agent=request.agent,
            style_ids=request.style_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    variants = [
        PromptStyleVariant(
            style_id=v["style_id"],
            style_name=v["style_name"],
            style_name_zh=v["style_name_zh"],
            prompt=v["prompt"],
            scores=v["scores"],
            total_score=v["total_score"],
            highlights=v.get("highlights") or [],
            recommended=v["style_id"] == result["recommended_style_id"],
        )
        for v in result["variants"]
    ]
    return PromptOptimizeResponse(
        original=result.get("original") or text,
        recommended_style_id=result["recommended_style_id"],
        recommended_prompt=result["recommended_prompt"],
        rationale=result.get("rationale") or "",
        variants=variants,
        ai_applied=bool(result.get("ai_applied")),
        message="优化完成" if result.get("ai_applied") else "已使用模板回退生成",
    )

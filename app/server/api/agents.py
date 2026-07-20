# =============================================================================
# Agent 元数据 HTTP API。
#
# 职责：
#     1. 列出可用 Agent 角色、描述与默认工具白名单摘要
#     2. 暴露 RAG / MCP 启用状态供前端展示
#     3. 只读元数据，不执行对话
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/agents/config.py、server/config.py
#
# 阅读提示：
#     - 新人先看 list_agents 与 _AGENT_DESCRIPTIONS
#
# Debug：
#     - 角色缺失 → AGENT_NAMES 与前端枚举不一致
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter

from server.agents.config import AGENT_NAMES, get_agent_default_whitelist
from server.config import get_settings
from shared.schemas import AgentInfo, AgentListResponse

router = APIRouter(tags=["agents"])

_AGENT_DESCRIPTIONS: dict[str, str] = {
    "general": "通用科研问答与总结",
    "theory": "数学推导、定理证明与损失函数理论",
    "experiment": "数值验证、Hessian 谱与 loss landscape 实验",
    "literature": "文献检索、论文综述与引用整理",
    "review": "理论推导审稿与清单检查",
}


@router.get("/v1/agents", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """列出可用 Agent 角色及 RAG / 默认工具白名单。"""
    settings = get_settings()
    rag_names = set(settings.rag_agent_names())
    agents = [
        AgentInfo(
            name=name,
            description=_AGENT_DESCRIPTIONS.get(name, ""),
            rag_enabled=name in rag_names and settings.enable_rag,
            default_tool_patterns=get_agent_default_whitelist(name),
        )
        for name in AGENT_NAMES
    ]
    return AgentListResponse(
        orchestration_backend=settings.orchestration_backend,
        agents=agents,
    )

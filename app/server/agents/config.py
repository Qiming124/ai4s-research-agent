# =============================================================================
# Agent 注册表与配置常量。
#
# 职责：
#     1. 定义 AgentName 字面量类型与 AGENT_NAMES 列表
#     2. 维护各 Agent 的系统提示词（AGENT_PROMPTS）
#     3. 提供 normalize_agent_name() 与 get_agent_default_whitelist()
#
# 架构位置：
#     - 被调用：server/agents/orchestrator.py、subagent.py、server/api/agents.py、
#               server/graph/router_llm.py、research_supervisor.py
#     - 调用：server/llm/prompts.py（各角色专用 prompt 常量）
#
# 阅读提示：
#     - 新人先看 AGENT_NAMES 与 AGENT_PROMPTS 映射
#     - 工具白名单见 get_agent_default_whitelist()
#
# Debug：
#     - 未知 Agent 名 → normalize_agent_name 回退 general
#     - 子 Agent 工具过多 → 检查 whitelist 模式与 MCP 白名单配置
# =============================================================================

from __future__ import annotations

from typing import Literal

from server.llm.prompts import (
    COUNTEREXAMPLE_AGENT_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    EXPERIMENT_AGENT_PROMPT,
    LITERATURE_AGENT_PROMPT,
    REVIEW_AGENT_PROMPT,
    THEORY_AGENT_PROMPT,
)

AgentName = Literal["general", "theory", "experiment", "literature", "review", "counterexample"]

AGENT_NAMES: tuple[AgentName, ...] = (
    "general",
    "theory",
    "experiment",
    "literature",
    "review",
    "counterexample",
)

_AGENT_PROMPTS: dict[AgentName, str] = {
    "general": DEFAULT_SYSTEM_PROMPT,
    "theory": THEORY_AGENT_PROMPT,
    "experiment": EXPERIMENT_AGENT_PROMPT,
    "literature": LITERATURE_AGENT_PROMPT,
    "review": REVIEW_AGENT_PROMPT,
    "counterexample": COUNTEREXAMPLE_AGENT_PROMPT,
}

# 内置默认白名单（可被 mcp_tool_whitelist.json agents 覆盖）
_AGENT_DEFAULT_WHITELIST: dict[AgentName, list[str]] = {
    "general": ["*"],
    "theory": ["sympy__*", "numerical__*", "rag__*", "web_search__*"],
    "experiment": ["filesystem__*", "numerical__*"],
    "literature": ["arxiv__*", "web_search__*"],
    "review": ["filesystem__*"],
    "counterexample": ["sympy__*", "numerical__*"],
}


def get_agent_prompt(name: AgentName) -> str:
    return _AGENT_PROMPTS[name]


def get_agent_default_whitelist(name: AgentName) -> list[str]:
    return list(_AGENT_DEFAULT_WHITELIST[name])


def normalize_agent_name(value: str | None) -> AgentName | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in AGENT_NAMES:
        return normalized  # type: ignore[return-value]
    return None

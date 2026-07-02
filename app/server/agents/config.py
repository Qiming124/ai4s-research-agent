# Agent 注册表：名称、提示词、默认工具白名单模式。

from __future__ import annotations

from typing import Literal

from server.llm.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    EXPERIMENT_AGENT_PROMPT,
    LITERATURE_AGENT_PROMPT,
    REVIEW_AGENT_PROMPT,
    THEORY_AGENT_PROMPT,
)

AgentName = Literal["general", "theory", "experiment", "literature", "review"]

AGENT_NAMES: tuple[AgentName, ...] = (
    "general",
    "theory",
    "experiment",
    "literature",
    "review",
)

_AGENT_PROMPTS: dict[AgentName, str] = {
    "general": DEFAULT_SYSTEM_PROMPT,
    "theory": THEORY_AGENT_PROMPT,
    "experiment": EXPERIMENT_AGENT_PROMPT,
    "literature": LITERATURE_AGENT_PROMPT,
    "review": REVIEW_AGENT_PROMPT,
}

# 内置默认白名单（可被 mcp_tool_whitelist.json agents 覆盖）
_AGENT_DEFAULT_WHITELIST: dict[AgentName, list[str]] = {
    "general": ["*"],
    "theory": ["sympy__*", "numerical__*", "rag__*", "web_search__*"],
    "experiment": ["filesystem__*", "numerical__*"],
    "literature": ["arxiv__*", "web_search__*"],
    "review": ["filesystem__*"],
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

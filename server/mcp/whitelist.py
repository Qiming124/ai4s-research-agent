# MCP 工具白名单：按 glob 模式过滤 OpenAI tools 列表。

from __future__ import annotations

import json
import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from server.config import Settings
from server.agents.config import get_agent_default_whitelist, normalize_agent_name

logger = logging.getLogger(__name__)


def _parse_csv_patterns(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def _load_whitelist_config(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        logger.warning("MCP 工具白名单文件不存在: %s", file_path)
        return {}
    try:
        with file_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取 MCP 工具白名单失败: %s — %s", file_path, exc)
        return {}


def resolve_whitelist_patterns(
    settings: Settings,
    agent_name: str | None = None,
) -> list[str]:
    patterns: list[str] = []
    agent_patterns_from_config: list[str] = []

    if settings.mcp_tool_whitelist_path:
        config = _load_whitelist_config(settings.mcp_tool_whitelist_path)
        patterns.extend(_parse_csv_patterns(",".join(config.get("global", []))))
        agents = config.get("agents", {})
        if agent_name and isinstance(agents, dict):
            agent_patterns = agents.get(agent_name, [])
            if isinstance(agent_patterns, list):
                agent_patterns_from_config = [str(p) for p in agent_patterns]
                patterns.extend(agent_patterns_from_config)

    patterns.extend(_parse_csv_patterns(settings.mcp_tool_whitelist))

    if agent_name and not agent_patterns_from_config:
        normalized = normalize_agent_name(agent_name)
        if normalized and not settings.mcp_tool_whitelist:
            patterns.extend(get_agent_default_whitelist(normalized))

    return patterns


def tool_matches_whitelist(qualified_name: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    for pattern in patterns:
        if pattern == "*" or fnmatch(qualified_name, pattern):
            return True
    return False


def filter_openai_tools(
    tools: list[dict[str, Any]],
    settings: Settings,
    agent_name: str | None = None,
) -> list[dict[str, Any]]:
    patterns = resolve_whitelist_patterns(settings, agent_name)
    if not patterns:
        return tools
    filtered = [
        tool
        for tool in tools
        if tool_matches_whitelist(tool["function"]["name"], patterns)
    ]
    if not filtered and tools:
        logger.warning(
            "MCP 工具白名单过滤后无可用工具 (agent=%s, patterns=%s)",
            agent_name,
            patterns,
        )
    return filtered

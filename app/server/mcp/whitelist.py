# =============================================================================
# MCP 工具白名单：按 glob 模式过滤 OpenAI tools 列表。
#
# 过滤层级（优先级从高到低）：
#     1. mcp_tool_whitelist.json → agents.{name}  按 Agent 指定
#     2. mcp_tool_whitelist.json → global          全 Agent 共享
#     3. conf/.env MCP_TOOL_WHITELIST              逗号分隔 glob（如 filesystem__*）
#     4. 代码内置默认白名单（get_agent_default_whitelist）
#
# glob 匹配：fnmatch（支持 * ? [...] 模式）。
# 特殊值："*" 通过全部工具，"__none__" 禁止全部工具。
# =============================================================================

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
    """将逗号分隔字符串解析为 glob 模式列表。去首尾空格，跳过空项。"""
    return [p.strip() for p in value.split(",") if p.strip()]


def _load_whitelist_config(path: str | Path) -> dict[str, Any]:
    """
    从 JSON 文件加载白名单配置。

    期望格式：
        {
            "global": ["filesystem__*"],
            "agents": {
                "theory": ["__none__"],
                "literature": ["arxiv__*", "web_search__*"]
            }
        }

    返回:
        解析后的字典；文件不存在或解析失败时返回空 dict
    """
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
    """
    解析最终生效的白名单 glob 模式列表。

    合并顺序（后面的追加，不覆盖）：
        1. JSON 文件的 global 列表
        2. JSON 文件的 agents.{name} 列表
        3. .env MCP_TOOL_WHITELIST（CSV）
        4. 代码内置默认白名单（仅当 JSON 未指定且 CSV 为空时）

    参数:
        settings: 运行时配置
        agent_name: 当前 Agent 名（如 theory）；None 则只用 global

    返回:
        glob 模式列表；空列表表示不过滤（通过全部工具）
    """
    patterns: list[str] = []
    agent_patterns_from_config: list[str] = []

    # 第一级：JSON 白名单文件
    if settings.mcp_tool_whitelist_path:
        config = _load_whitelist_config(settings.mcp_tool_whitelist_path)
        # global 模式
        patterns.extend(_parse_csv_patterns(",".join(config.get("global", []))))
        # agent 专属模式
        agents = config.get("agents", {})
        if agent_name and isinstance(agents, dict):
            agent_patterns = agents.get(agent_name, [])
            if isinstance(agent_patterns, list):
                agent_patterns_from_config = [str(p) for p in agent_patterns]
                patterns.extend(agent_patterns_from_config)

    # 第二级：.env MCP_TOOL_WHITELIST（CSV）
    patterns.extend(_parse_csv_patterns(settings.mcp_tool_whitelist))

    # 第三级：代码内置默认白名单（仅当上两级都未指定时启用）
    if agent_name and not agent_patterns_from_config:
        normalized = normalize_agent_name(agent_name)
        if normalized and not settings.mcp_tool_whitelist:
            patterns.extend(get_agent_default_whitelist(normalized))

    return patterns


def tool_matches_whitelist(qualified_name: str, patterns: list[str]) -> bool:
    """
    判断工具是否匹配任一白名单模式。

    patterns 为空 → 不限制（全部通过）
    任一 pattern 匹配 → 通过
    """
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
    """
    按白名单模式过滤 OpenAI tools 列表。

    参数:
        tools: 完整的 OpenAI tools 列表（来自 ToolRegistry.to_openai_tools）
        settings: 运行时配置
        agent_name: 当前 Agent 名；None=不应用 Agent 专属白名单

    返回:
        过滤后的 tools 列表；若过滤后为空且输入非空，记录 warning
    """
    patterns = resolve_whitelist_patterns(settings, agent_name)
    if not patterns:
        return tools  # 无限制，全部通过
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

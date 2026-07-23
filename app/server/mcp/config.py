# =============================================================================
# MCP Server 配置加载。
#
# 职责：
#     1. 从 mcp_servers.json 读取各 Server 的启动配置
#     2. 支持 `${VAR}` 环境变量替换
#     3. 构建 langchain-mcp-adapters 所需的 StdioConnection 字典
#
# mcp_servers.json 格式：
#     {
#         "server_name": {
#             "command": "python" 或 "npx" 或可执行文件路径,
#             "args": ["-m", "mcp_module"],
#             "env": { "API_KEY": "${MY_API_KEY}" },
#             "enabled": true
#         }
#     }
#
# ${VAR} 在加载时替换为当前环境变量值，未设置时替换为空字符串。
# =============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StdioConnection
from pydantic import BaseModel, Field

from shared.paths import PROJECT_ROOT, conf_path

import logging

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """单个 MCP Server 的配置模型。"""
    command: str                                    # 启动命令（python / npx / 绝对路径）
    args: list[str] = Field(default_factory=list)   # 命令行参数列表
    env: dict[str, str] = Field(default_factory=dict)  # 环境变量（已展开 ${VAR}）
    enabled: bool = True                            # 是否启用此 Server


def resolve_mcp_config_path(config_path: str | Path) -> Path:
    """
    解析 mcp_servers.json 路径：相对路径相对仓库根；文件不存在时回退到 conf/mcp_servers.json。
    """
    path = Path(config_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    if path.is_file():
        return path
    fallback = conf_path("mcp_servers.json")
    if fallback.is_file() and path != fallback:
        logger.warning(
            "MCP 配置不存在: %s，回退到 %s",
            config_path,
            fallback,
        )
        return fallback
    return path


def _expand_env(value: str) -> str:
    """
    替换字符串中的 ${VAR} 引用为对应环境变量值。

    例如："${HOME}" → "/home/user"、"${UNDEFINED}" → ""
    """
    def replacer(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.environ.get(var, "")

    return re.sub(r"\$\{([^}]+)\}", replacer, value)


def sync_mcp_runtime_env(settings: "Settings | None" = None) -> None:
    """
    将 conf/.env 中的 MCP 相关配置同步到 os.environ，
    供 mcp_servers.json 的 ${VAR} 展开及 stdio 子进程继承。
    """
    from server.config import get_settings

    s = settings or get_settings()
    if not os.environ.get("MCP_ALLOWED_DIRS"):
        os.environ["MCP_ALLOWED_DIRS"] = s.mcp_allowed_dirs
    if s.tavily_api_key and not os.environ.get("TAVILY_API_KEY"):
        os.environ["TAVILY_API_KEY"] = s.tavily_api_key


def load_mcp_servers(config_path: str | Path) -> dict[str, MCPServerConfig]:
    """
    从 mcp_servers.json 加载全部已启用 Server 配置。

    参数:
        config_path: JSON 配置文件路径

    返回:
        {server_name: MCPServerConfig} 字典；文件不存在或为空时返回 {}
    """
    path = resolve_mcp_config_path(config_path)
    if not path.is_file():
        return {}

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    servers: dict[str, MCPServerConfig] = {}

    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        # 展开 env 中的 ${VAR} 引用
        env = {k: _expand_env(str(v)) for k, v in entry.get("env", {}).items()}
        servers[name] = MCPServerConfig(
            command=entry["command"],
            args=entry.get("args", []),
            env=env,
            enabled=entry.get("enabled", True),
        )
    return servers


def build_multiserver_connections(
    configs: dict[str, MCPServerConfig],
) -> dict[str, StdioConnection]:
    """
    将加载的 MCPServerConfig 字典转为 MultiServerMCPClient 所需的 stdio 连接字典。

    特殊处理：command 为 "python" 时替换为 sys.executable（当前 Python 解释器路径），
    确保子进程使用正确的 Python 环境。

    始终合并父进程环境，并保证 PYTHONPATH 含仓库 app/，避免子进程
    `No module named 'server.config'`。
    """
    connections: dict[str, StdioConnection] = {}
    app_dir = str(Path(__file__).resolve().parents[2])  # .../app
    parent_env = dict(os.environ)
    existing_pp = parent_env.get("PYTHONPATH", "")
    pp_parts = [p for p in existing_pp.split(os.pathsep) if p]
    if app_dir not in pp_parts:
        pp_parts.insert(0, app_dir)
    parent_env["PYTHONPATH"] = os.pathsep.join(pp_parts)

    for name, cfg in configs.items():
        if not cfg.enabled:
            continue

        command = sys.executable if cfg.command == "python" else cfg.command
        merged = dict(parent_env)
        if cfg.env:
            for k, v in cfg.env.items():
                if v:
                    merged[k] = v
        connection: StdioConnection = {
            "transport": "stdio",
            "command": command,
            "args": list(cfg.args),
            "env": merged,
        }
        connections[name] = connection

    return connections


def create_multiserver_client(
    configs: dict[str, MCPServerConfig],
) -> MultiServerMCPClient:
    """
    从 MCPServerConfig 创建 MultiServerMCPClient。

    参数:
        configs: load_mcp_servers() 的返回值

    返回:
        MultiServerMCPClient 实例（按 connections 创建，调用 .connect 建立连接）
    """
    return MultiServerMCPClient(build_multiserver_connections(configs))

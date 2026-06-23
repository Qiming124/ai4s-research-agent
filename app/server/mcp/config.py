# MCP Server 配置加载。

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


class MCPServerConfig(BaseModel):
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


def _expand_env(value: str) -> str:
    """将 ${VAR} 替换为环境变量值。"""
    def replacer(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.environ.get(var, "")

    return re.sub(r"\$\{([^}]+)\}", replacer, value)


def load_mcp_servers(config_path: str | Path) -> dict[str, MCPServerConfig]:
    path = Path(config_path)
    if not path.exists():
        return {}

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    servers: dict[str, MCPServerConfig] = {}

    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
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
    """Convert loaded MCP server configs to MultiServerMCPClient stdio connections."""
    connections: dict[str, StdioConnection] = {}

    for name, cfg in configs.items():
        if not cfg.enabled:
            continue

        command = sys.executable if cfg.command == "python" else cfg.command
        connection: StdioConnection = {
            "transport": "stdio",
            "command": command,
            "args": list(cfg.args),
        }
        if cfg.env:
            connection["env"] = dict(cfg.env)
        connections[name] = connection

    return connections


def create_multiserver_client(
    configs: dict[str, MCPServerConfig],
) -> MultiServerMCPClient:
    """Build a MultiServerMCPClient from mcp_servers.json-derived configs."""
    return MultiServerMCPClient(build_multiserver_connections(configs))

# MCPClient → LangChain StructuredTool 绑定。

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

if TYPE_CHECKING:
    from server.mcp.client import MCPClient


def _schema_to_pydantic(name: str, schema: dict[str, Any]) -> type:
    """将 JSON Schema properties 转为简易 Pydantic 模型（仅用于 tool args）。"""
    properties = schema.get("properties") or {}
    fields: dict[str, tuple[type, Any]] = {}
    for prop_name, prop_schema in properties.items():
        prop_type = str
        if isinstance(prop_schema, dict):
            json_type = prop_schema.get("type")
            if json_type == "integer":
                prop_type = int
            elif json_type == "number":
                prop_type = float
            elif json_type == "boolean":
                prop_type = bool
        fields[prop_name] = (prop_type, ...)
    if not fields:
        fields["__dummy"] = (str, "")
    return create_model(f"{name}Args", **fields)


def _make_tool(
    mcp: MCPClient,
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
) -> StructuredTool:
    args_schema = _schema_to_pydantic(name, input_schema)

    async def _call_tool(**kwargs: Any) -> str:
        clean_args = {k: v for k, v in kwargs.items() if k != "__dummy"}
        return await mcp.call_tool(name, clean_args)

    return StructuredTool.from_function(
        coroutine=_call_tool,
        name=name,
        description=description,
        args_schema=args_schema,
    )


def mcp_tools_to_langchain(
    mcp: MCPClient,
    *,
    agent_name: str | None = None,
) -> list[StructuredTool]:
    """从 MCPClient 注册表（或 OpenAI tools 列表）构建 LangChain StructuredTool。"""
    openai_tools = mcp.get_openai_tools(agent_name=agent_name)
    allowed_names = {t["function"]["name"] for t in openai_tools}
    tools: list[StructuredTool] = []

    registry = getattr(mcp, "registry", None)
    if registry is not None:
        for reg in registry.list_tools():
            if reg.qualified_name not in allowed_names:
                continue
            tools.append(
                _make_tool(
                    mcp,
                    name=reg.qualified_name,
                    description=reg.description,
                    input_schema=reg.input_schema,
                )
            )
        return tools

    for tool_def in openai_tools:
        fn = tool_def.get("function", {})
        name = fn.get("name", "")
        if not name:
            continue
        tools.append(
            _make_tool(
                mcp,
                name=name,
                description=fn.get("description") or "",
                input_schema=fn.get("parameters") or {"type": "object", "properties": {}},
            )
        )

    return tools

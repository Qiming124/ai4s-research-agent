# =============================================================================
# MCPClient → LangChain StructuredTool 绑定。
#
# 职责：将 MCPClient 的工具注册表转换为 LangChain 可绑定的 StructuredTool 列表。
#       LangGraph ReAct 子图需要 LangChain BaseTool 实例来执行 function calling。
#
# 转换过程：
#     1. 从 MCPClient.get_openai_tools 获取过滤后的工具定义
#     2. 为每个工具从 JSON Schema 构造简易 Pydantic 参数模型
#     3. 创建 StructuredTool（封装 call_tool 的异步调用）
#
# 限制：
#     - JSON Schema 复杂类型（oneOf/allOf/array of objects）转为 str 类型
#     - 这是 Phase 3 的临时桥接方案，后续可能直接使用 MCP 原生 adapter
# =============================================================================

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

if TYPE_CHECKING:
    from server.mcp.client import MCPClient


def _schema_to_pydantic(name: str, schema: dict[str, Any]) -> type:
    """
    将 JSON Schema properties 转为简易 Pydantic 模型类。

    类型映射（简化）：
        "string"  → str
        "integer" → int
        "number"  → float
        "boolean" → bool
        其他/缺失 → str（退化为字符串，由 tool 实现自行解析）

    参数:
        name: 模型名（用于 create_model 的 __name__）
        schema: JSON Schema 字典（至少含 properties 字段）

    返回:
        pydantic.BaseModel 的子类，每个 property 作为一个字段

    注：若 schema 无 properties，则生成一个 __dummy 字段确保模型非空。
    """
    properties = schema.get("properties") or {}
    fields: dict[str, tuple[type, Any]] = {}
    for prop_name, prop_schema in properties.items():
        prop_type = str  # 默认为字符串
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
        fields["__dummy"] = (str, "")  # 占位字段，确保模型非空
    return create_model(f"{name}Args", **fields)


def _make_tool(
    mcp: MCPClient,
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
) -> StructuredTool:
    """
    用 MCPClient.call_tool 包装单个工具为 LangChain StructuredTool。

    参数:
        mcp: MCP 客户端实例（用于实际执行 call_tool）
        name: qualified 工具名
        description: 工具描述
        input_schema: JSON Schema 参数定义

    返回:
        可 LangGraph bind_tools 的 StructuredTool
    """
    args_schema = _schema_to_pydantic(name, input_schema)

    async def _call_tool(**kwargs: Any) -> str:
        """
        StructuredTool 的执行体：去 __dummy 占位字段后调用 MCPClient.call_tool。
        """
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
    """
    从 MCPClient 注册表构建 LangChain StructuredTool 列表。

    参数:
        mcp: MCP 客户端实例
        agent_name: 可选 Agent 名（用于白名单过滤）

    返回:
        StructuredTool 列表，可直接传入 LangGraph build_react_graph

    实现：
        1. 调用 mcp.get_openai_tools(agent_name) 获取过滤后的工具定义
        2. 从 mcp.registry 获取完整的 input_schema
        3. 为每个在允许列表中的工具创建 StructuredTool
    """
    # 获取经白名单过滤后的工具名列表
    openai_tools = mcp.get_openai_tools(agent_name=agent_name)
    allowed_names = {t["function"]["name"] for t in openai_tools}
    tools: list[StructuredTool] = []

    # 优先从 ToolRegistry 获取完整的 input_schema
    registry = getattr(mcp, "registry", None)
    if registry is not None:
        for reg in registry.list_tools():
            if reg.qualified_name not in allowed_names:
                continue  # 不在白名单中，跳过
            tools.append(
                _make_tool(
                    mcp,
                    name=reg.qualified_name,
                    description=reg.description,
                    input_schema=reg.input_schema,
                )
            )
        return tools

    # 回退：从 OpenAI tools 定义中提取信息（input_schema 精度有限）
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

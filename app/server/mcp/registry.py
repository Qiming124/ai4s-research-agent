# =============================================================================
# Tool 注册表：聚合多个 MCP Server 的工具 schema。
#
# 职责：
#     1. 维护 qualified_name（"{server}__{tool}"）→ RegisteredTool 映射
#     2. 提供 OpenAI function-calling 格式的 tools 列表（to_openai_tools）
#     3. 作为 MCPClient 内部的数据结构，供 call_tool 凭名查找
#
# 架构位置：
#     MCPClient.connect()  → registry.register()  逐个 Server 注册工具
#     MCPClient.call_tool() → registry.get()      凭名查找
#     GeneralAgent.run()   → .get_openai_tools()  传给 LLM function calling
#
# 工具命名规则："{server_name}__{tool_name}"，避免不同 Server 同名工具冲突。
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisteredTool:
    """单个已注册 MCP 工具的元数据。"""
    qualified_name: str                          # 全局唯一名，如 web_search__search
    server_name: str                            # Server 名
    tool_name: str                              # Server 内工具名（无前缀）
    description: str                            # 人类可读描述
    input_schema: dict[str, Any]                # JSON Schema 参数定义


@dataclass
class ToolRegistry:
    """
    工具注册表：{qualified_name → RegisteredTool} 映射。

    供 MCPClient 在 connect 时填充，call_tool 时查找。
    """
    tools: dict[str, RegisteredTool] = field(default_factory=dict)

    def register(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        """
        注册一个 MCP 工具到全局命名空间。

        参数:
            server_name: MCP Server 名（如 arxiv）
            tool_name: 工具名（如 search_papers）
            description: 工具功能说明
            input_schema: JSON Schema 字典，定义工具输入参数格式
        """
        # 拼接 qualified_name：{server}__{tool}，确保不同 Server 的同名工具可区分
        qualified = f"{server_name}__{tool_name}"
        self.tools[qualified] = RegisteredTool(
            qualified_name=qualified,
            server_name=server_name,
            tool_name=tool_name,
            description=description or "",
            input_schema=input_schema or {"type": "object", "properties": {}},
        )

    def get(self, qualified_name: str) -> RegisteredTool | None:
        """按 qualified_name 查找工具。返回 None 表未注册。"""
        return self.tools.get(qualified_name)

    def list_tools(self) -> list[RegisteredTool]:
        """列出所有已注册工具（不含过滤）。"""
        return list(self.tools.values())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """
        转为 OpenAI Chat Completions API 的 tools 参数格式。

        每条工具：
            type: "function"
            function.name: qualified_name（如 filesystem__read_file）
            function.description: 工具描述
            function.parameters: input_schema JSON Schema
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.qualified_name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.tools.values()
        ]

    def clear(self) -> None:
        """清空注册表（关闭连接或重置时调用）。"""
        self.tools.clear()

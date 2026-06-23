# Tool 注册表：聚合多个 MCP Server 的工具 schema。

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisteredTool:
    qualified_name: str
    server_name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolRegistry:
    tools: dict[str, RegisteredTool] = field(default_factory=dict)

    def register(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        qualified = f"{server_name}__{tool_name}"
        self.tools[qualified] = RegisteredTool(
            qualified_name=qualified,
            server_name=server_name,
            tool_name=tool_name,
            description=description or "",
            input_schema=input_schema or {"type": "object", "properties": {}},
        )

    def get(self, qualified_name: str) -> RegisteredTool | None:
        return self.tools.get(qualified_name)

    def list_tools(self) -> list[RegisteredTool]:
        return list(self.tools.values())

    def to_openai_tools(self) -> list[dict[str, Any]]:
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
        self.tools.clear()

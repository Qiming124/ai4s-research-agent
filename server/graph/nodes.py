# ReAct 子图节点：call_model、execute_tools、call_model_final。

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from server.graph.state import ReactState
from server.mcp.truncation import truncate_tool_result
from shared.schemas import PersistedToolCall

logger = logging.getLogger(__name__)


def make_call_model_node(
    model: BaseChatModel,
    tools: list[BaseTool],
) -> Any:
    """工具轮次：绑定 tools，关闭 thinking。"""
    bound = model.bind_tools(tools)

    async def call_model(state: ReactState, config: RunnableConfig) -> dict[str, Any]:
        response = await bound.ainvoke(state["messages"], config)
        return {"messages": [response]}

    return call_model


def make_execute_tools_node(
    mcp_tools: list[BaseTool],
    *,
    max_result_chars: int,
) -> Any:
    """执行工具、截断结果写入 ToolMessage，并收集 PersistedToolCall。"""
    tools_by_name = {tool.name: tool for tool in mcp_tools}

    async def execute_tools(state: ReactState, config: RunnableConfig) -> dict[str, Any]:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}

        tool_messages: list[ToolMessage] = []
        records: list[PersistedToolCall] = []

        for tc in last.tool_calls:
            tc_id = tc["id"]
            tc_name = tc["name"]
            tc_args = tc.get("args") or {}
            args_json = json.dumps(tc_args, ensure_ascii=False)

            record = PersistedToolCall(
                id=tc_id,
                name=tc_name,
                arguments=args_json,
            )

            tool = tools_by_name.get(tc_name)
            try:
                if tool is None:
                    raise ValueError(f"未知工具: {tc_name}")
                raw_result = await tool.ainvoke(tc_args, config)
                if not isinstance(raw_result, str):
                    raw_result = json.dumps(raw_result, ensure_ascii=False)
                record.result = raw_result
                record.status = "success"
                truncated = truncate_tool_result(raw_result, max_result_chars)
            except Exception as exc:
                err_text = f"工具调用失败: {exc}"
                record.status = "error"
                record.error = err_text
                truncated = err_text

            records.append(record)
            tool_messages.append(
                ToolMessage(content=truncated, tool_call_id=tc_id, name=tc_name)
            )

        return {
            "messages": tool_messages,
            "tool_call_records": records,
            "tool_rounds": state.get("tool_rounds", 0) + 1,
        }

    return execute_tools


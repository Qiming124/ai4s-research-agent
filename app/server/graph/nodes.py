# =============================================================================
# ReAct 子图节点：call_model、execute_tools。
#
# 职责：LangGraph ReAct 工具循环中的两个核心节点函数。
#
# 节点流程：
#     1. call_model      → 绑定工具，调 LLM（thinking off）
#     2. execute_tools   → 执行 tool_calls，截断结果，收集 PersistedToolCall
#     3. 循环直到 LLM 不返回 tool_calls 或达到上限
#
# 架构位置：
#     graph/react.py → build_react_graph 调用 make_call_model_node / make_execute_tools_node
#     graph/streaming.py → stream_react_graph 消费 execute_tools 产出的 tool_call_records
# =============================================================================

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
    """
    创建 call_model 节点函数：绑定工具后调 LLM（thinking=off）。

    参数:
        model: 已配置 thinking=off 的 LangChain ChatOpenAI 实例
        tools: LangChain StructuredTool 列表

    返回:
        异步节点函数 call_model(state, config) → {"messages": [...]}

    节点行为：
        - 将 tools 绑定到 model（model.bind_tools(tools)）
        - 传入当前 state 的 messages 列表
        - 返回 LLM 的 AIMessage 响应（可能含 tool_calls，也可能含 content）
    """
    # 绑定工具到模型，使 LLM 可以请求 function calling
    bound = model.bind_tools(tools)

    async def call_model(state: ReactState, config: RunnableConfig) -> dict[str, Any]:
        """
        调用绑定了工具的 LLM，返回 AIMessage 追加到 messages 列表。

        参数:
            state: ReactState，含 messages / tool_call_records / tool_rounds
            config: LangGraph RunnableConfig（含 callbacks 等）
        """
        response = await bound.ainvoke(state["messages"], config)
        return {"messages": [response]}

    return call_model


def make_execute_tools_node(
    mcp_tools: list[BaseTool],
    *,
    max_result_chars: int,
) -> Any:
    """
    创建 execute_tools 节点函数：执行 AIMessage 中的 tool_calls。

    参数:
        mcp_tools: LangChain StructuredTool 列表（用于按名查找工具实例）
        max_result_chars: 工具结果截断上限字符数

    返回:
        异步节点函数 execute_tools(state, config) → {"messages": [...], "tool_call_records": [...], "tool_rounds": int}

    节点行为：
        1. 取最后一条 AIMessage 的 tool_calls
        2. 逐个按名查找工具并调用
        3. 成功 → result 存入 PersistedToolCall；失败 → status=error + error 文本
        4. 截断超过 max_result_chars 的结果
        5. 将截断后的结果写入 ToolMessage，追加到 messages
        6. tool_rounds 递增

    产出：
        返回字典含 messages（ToolMessage 列表）、tool_call_records（PersistedToolCall 列表）、
        tool_rounds（当前轮次计数）。stream_react_graph 消费 tool_call_records 转为 SSE 事件。
    """
    # 构建工具名 → 工具实例的索引，加速按名查找
    tools_by_name = {tool.name: tool for tool in mcp_tools}

    async def execute_tools(state: ReactState, config: RunnableConfig) -> dict[str, Any]:
        """
        执行 AIMessage 中请求的全部工具调用。

        参数:
            state: ReactState，messages 最后一条应为含 tool_calls 的 AIMessage
            config: LangGraph RunnableConfig
        """
        last = state["messages"][-1]
        # 确保最后一条消息是 AIMessage 且含有 tool_calls
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}

        tool_messages: list[ToolMessage] = []
        records: list[PersistedToolCall] = []

        for tc in last.tool_calls:
            tc_id = tc["id"]
            tc_name = tc["name"]
            tc_args = tc.get("args") or {}
            args_json = json.dumps(tc_args, ensure_ascii=False)

            # 创建持久化工具调用记录（初始 status=success）
            record = PersistedToolCall(
                id=tc_id,
                name=tc_name,
                arguments=args_json,
            )

            tool = tools_by_name.get(tc_name)
            try:
                if tool is None:
                    raise ValueError(f"未知工具: {tc_name}")
                # 调用工具（ainvoke 异步执行）
                raw_result = await tool.ainvoke(tc_args, config)
                # 如果工具返回的不是字符串，转为 JSON 字符串
                if not isinstance(raw_result, str):
                    raw_result = json.dumps(raw_result, ensure_ascii=False)
                record.result = raw_result
                record.status = "success"
                # 截断超过上限的结果，避免挤爆 LLM 上下文窗口
                truncated = truncate_tool_result(raw_result, max_result_chars)
            except Exception as exc:
                # 工具调用失败：记录错误，错误消息同时作为 ToolMessage 内容
                err_text = f"工具调用失败: {exc}"
                record.status = "error"
                record.error = err_text
                truncated = err_text

            records.append(record)
            # 构建 ToolMessage（OpenAI 格式，含 tool_call_id 标识来源）
            tool_messages.append(
                ToolMessage(content=truncated, tool_call_id=tc_id, name=tc_name)
            )

        return {
            "messages": tool_messages,
            "tool_call_records": records,
            "tool_rounds": state.get("tool_rounds", 0) + 1,  # 累计轮次 +1
        }

    return execute_tools

# =============================================================================
# ReAct 子图状态定义。
#
# 职责：LangGraph ReAct 工具循环子图共享的状态类型。
#
# 字段：
#     messages: LangChain BaseMessage 列表，使用 add_messages reducer 自动合并
#     tool_call_records: 持久化工具调用记录列表，使用 operator.add 追加
#     tool_rounds: 工具调用轮次计数器
#
# LangGraph TypedDict State：
#     Annotated[type, reducer] — reducer 定义状态更新时如何合并新旧值。
#     add_messages: 新消息追加到列表末尾
#     operator.add: 新值追加到列表
#     int: 直接覆盖
# =============================================================================

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from shared.schemas import PersistedToolCall


class ReactState(TypedDict):
    """
    LangGraph ReAct 子图状态。

    被 build_react_graph / stream_react_graph / nodes 节点共享，
    每次节点执行返回的 dict 按各字段的 reducer 自动合并入全局状态。

    字段详解：
        messages: 对话消息链（System → User → AIMessage → ToolMessage → ...）
                  add_messages reducer 保证新消息追加到末尾而非覆盖
        
        tool_call_records: 持久化工具调用记录，operator.add 在每次 execute_tools
                          执行后将新 Records 追加，供最终写入 L2 会话

        tool_rounds: 当前工具调用轮次（直接覆盖），用于限制最大轮次
    """
    messages: Annotated[list[BaseMessage], add_messages]
    tool_call_records: Annotated[list[PersistedToolCall], operator.add]
    tool_rounds: int

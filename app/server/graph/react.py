# =============================================================================
# ReAct 子图编译入口。
#
# 职责：构建 LangGraph ReAct 工具循环子图（call_model ↔ execute_tools 节点）。
#
# 图结构（Mermaid）：
#     ┌──────────┐   有 tool_calls    ┌──────────────┐
#     │ call_model ├────────────────→ │ execute_tools │
#     └─────┬──────┘                  └──────┬───────┘
#           │ 无 tool_calls                  │
#           ↓                                │
#          END  ←────────────────────────────┘
#
# 限制：
#     - max_tool_rounds：防止无限循环（默认 10 轮）
#     - tool_rounds >= max_tool_rounds 时：execute_tools 后直接 END
#       （禁止再 call_model，否则易产生悬空 tool_calls → DeepSeek 400）
#
# OpenAI dict → LangChain BaseMessage 转换：
#     messages_from_api_dicts 负责将 Legacy 路径的 dict 消息转为 LangGraph 可用的类型。
# =============================================================================

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph

from server.graph.nodes import make_call_model_node, make_execute_tools_node
from server.graph.state import ReactState


def messages_from_api_dicts(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """
    将 OpenAI 风格的 dict 消息列表转为 LangChain BaseMessage 列表。

    映射规则：
        role=system     → SystemMessage
        role=user       → HumanMessage
        role=assistant  → AIMessage（含可选 tool_calls 子结构）
        role=tool       → ToolMessage（含 tool_call_id）

    参数:
        messages: [{"role": ..., "content": ..., "tool_calls": [...]}, ...]

    返回:
        BaseMessage 列表，可直接传入 LangGraph StateGraph
    """
    result: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            additional: dict[str, Any] = {}
            if tool_calls:
                # DeepSeek：含 tool_calls 时必须带 reasoning_content（可为空）
                additional["reasoning_content"] = msg.get("reasoning_content") or ""
            elif msg.get("reasoning_content"):
                additional["reasoning_content"] = msg["reasoning_content"]
            if tool_calls:
                # assistant 消息含 tool_calls → 解析为 LangChain 格式
                lc_tool_calls = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    args_raw = fn.get("arguments", "{}")
                    # 兼容两种格式：字符串 JSON 或已解析的 dict
                    if isinstance(args_raw, str):
                        import json

                        try:
                            args = json.loads(args_raw) if args_raw else {}
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = args_raw
                    lc_tool_calls.append(
                        {
                            "id": tc["id"],
                            "name": fn.get("name", ""),
                            "args": args,
                        }
                    )
                result.append(
                    AIMessage(
                        content=content,
                        tool_calls=lc_tool_calls,
                        additional_kwargs=additional,
                    )
                )
            else:
                result.append(
                    AIMessage(
                        content=content,
                        additional_kwargs=additional,
                    )
                )
        elif role == "tool":
            # 工具返回消息，含 tool_call_id 用于关联请求
            result.append(
                ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", ""),
                )
            )
    return result


def _route_after_call_model(
    state: ReactState,
    *,
    max_tool_rounds: int,
) -> str:
    """
    条件路由：根据 AIMessage 是否含 tool_calls 决定下一步。

    规则：
        - AIMessage 且含 tool_calls 且未达回合上限 → "execute_tools"
        - 否则 → END（对话结束）

    注意：若已达上限仍返回 tool_calls，绝不能直接 END（会留下悬空 tool_calls，
    DeepSeek 最终合成 400）。此时仍走 execute_tools，由 _route_after_execute_tools
    在执行后结束；或由出站 sanitize 补占位。优先执行最后一轮工具。
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        # 有 tool_calls 必须先执行；达上限由 _route_after_execute_tools 结束。
        return "execute_tools"

    return END


def _route_after_execute_tools(
    state: ReactState,
    *,
    max_tool_rounds: int,
) -> str:
    """执行完工具后：未达上限则继续 call_model，否则 END（不再多要一轮 tool_calls）。"""
    if state.get("tool_rounds", 0) >= max_tool_rounds:
        return END
    return "call_model"


def build_react_graph(
    model: BaseChatModel,
    tools: list[BaseTool],
    *,
    max_tool_rounds: int,
    max_result_chars: int,
) -> Any:
    """
    编译 LangGraph ReAct 工具循环子图。

    参数:
        model: thinking=off 的 LangChain ChatOpenAI 模型（工具调用用）
        tools: LangChain StructuredTool 列表
        max_tool_rounds: 最多工具调用轮次（达到后强制结束）
        max_result_chars: 工具结果截断上限

    返回:
        CompiledStateGraph（可调用 .ainvoke / .astream）

    图节点：
        call_model    — 调 LLM 获取 tool_calls
        execute_tools — 执行 tool_calls 并回填 ToolMessage

    图边：
        START → call_model
        call_model → execute_tools（有 tool_calls）
        call_model → END（无 tool_calls）
        execute_tools → call_model（未达上限）
        execute_tools → END（已达上限，避免再 call_model 产生悬空 tool_calls）
    """
    graph = StateGraph(ReactState)

    # 添加两个核心节点
    graph.add_node("call_model", make_call_model_node(model, tools))
    graph.add_node(
        "execute_tools",
        make_execute_tools_node(tools, max_result_chars=max_result_chars),
    )

    graph.set_entry_point("call_model")

    # 条件边：根据 call_model 输出决定下一步
    graph.add_conditional_edges(
        "call_model",
        lambda state: _route_after_call_model(state, max_tool_rounds=max_tool_rounds),
        {
            "execute_tools": "execute_tools",
            END: END,
        },
    )

    # 执行工具后：达上限则结束，否则回到 call_model
    graph.add_conditional_edges(
        "execute_tools",
        lambda state: _route_after_execute_tools(state, max_tool_rounds=max_tool_rounds),
        {
            "call_model": "call_model",
            END: END,
        },
    )

    return graph.compile()

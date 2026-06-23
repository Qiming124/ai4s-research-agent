# ReAct 子图编译入口。

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
    """将 OpenAI 风格 dict 消息转为 LangChain BaseMessage 列表。"""
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
            if tool_calls:
                lc_tool_calls = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    args_raw = fn.get("arguments", "{}")
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
                result.append(AIMessage(content=content, tool_calls=lc_tool_calls))
            else:
                result.append(AIMessage(content=content))
        elif role == "tool":
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
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        if state.get("tool_rounds", 0) >= max_tool_rounds:
            return END
        return "execute_tools"

    return END


def build_react_graph(
    model: BaseChatModel,
    tools: list[BaseTool],
    *,
    max_tool_rounds: int,
    max_result_chars: int,
) -> Any:
    """编译 ReAct 工具循环子图：call_model ↔ execute_tools。"""
    graph = StateGraph(ReactState)
    graph.add_node("call_model", make_call_model_node(model, tools))
    graph.add_node(
        "execute_tools",
        make_execute_tools_node(tools, max_result_chars=max_result_chars),
    )

    graph.set_entry_point("call_model")
    graph.add_conditional_edges(
        "call_model",
        lambda state: _route_after_call_model(state, max_tool_rounds=max_tool_rounds),
        {
            "execute_tools": "execute_tools",
            END: END,
        },
    )
    graph.add_edge("execute_tools", "call_model")

    return graph.compile()

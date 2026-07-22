# DeepSeek thinking + tool_calls 消息回传兼容

from __future__ import annotations

from langgraph.graph import END

from server.llm.thinking_messages import (
    assistant_message_with_tools,
    ensure_reasoning_content_for_tool_messages,
    has_assistant_tool_calls,
    prepare_messages_for_deepseek,
    resolve_thinking_for_messages,
    sanitize_tool_call_pairing,
)
from shared.schemas import ChatMessage, PersistedToolCall
from server.agents.subagent import SubAgent
from server.config import get_settings
from server.graph.react import _route_after_execute_tools


def test_ensure_adds_empty_reasoning_for_tool_assistant():
    msgs = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search__search", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "ok"},
    ]
    out = ensure_reasoning_content_for_tool_messages(msgs)
    assert out[1]["reasoning_content"] == ""
    assert "reasoning_content" not in out[0]


def test_ensure_preserves_existing_reasoning():
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "plan A",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "x", "arguments": "{}"},
                }
            ],
        }
    ]
    out = ensure_reasoning_content_for_tool_messages(msgs)
    assert out[0]["reasoning_content"] == "plan A"


def test_has_assistant_tool_calls():
    with_tools = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "x", "arguments": "{}"},
                }
            ],
        },
    ]
    without = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    assert has_assistant_tool_calls(with_tools) is True
    assert has_assistant_tool_calls(without) is False


def test_resolve_thinking_disables_when_tool_calls_present():
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "x", "arguments": "{}"},
                }
            ],
        }
    ]
    assert resolve_thinking_for_messages(msgs, True) is False
    assert resolve_thinking_for_messages(msgs, False) is False


def test_resolve_thinking_keeps_requested_without_tool_calls():
    msgs = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    assert resolve_thinking_for_messages(msgs, True) is True
    assert resolve_thinking_for_messages(msgs, False) is False


def test_assistant_message_with_tools_defaults_empty_reasoning():
    msg = assistant_message_with_tools(
        content="hi",
        tool_calls=[
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "x", "arguments": "{}"},
            }
        ],
        reasoning_content=None,
    )
    assert msg["reasoning_content"] == ""
    assert msg["tool_calls"]


def test_build_messages_tool_history_gets_reasoning_placeholder():
    agent = SubAgent("general", settings=get_settings())
    history = [
        ChatMessage(
            role="assistant",
            content="used tools",
            reasoning_content=None,
            tool_calls=[PersistedToolCall(id="c1", name="web_search__search", arguments="{}")],
        ),
    ]
    msgs = agent._build_messages(history, "next", "sys")
    asst = [m for m in msgs if m["role"] == "assistant"][0]
    assert asst["reasoning_content"] == ""
    # 历史里的 tool_calls 元数据不得直接塞进 API（否则无 tool 回复会 400）
    assert "tool_calls" not in asst


def test_sanitize_fills_missing_tool_messages():
    """复现：达工具轮次上限后悬空 tool_calls → 须补齐 tool 消息。"""
    msgs = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search__search", "arguments": "{}"},
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "web_search__search", "arguments": "{}"},
                },
            ],
        },
        # 故意只给一条 tool，模拟中断 / 上限悬空
        {"role": "tool", "tool_call_id": "c1", "content": "partial"},
    ]
    out = sanitize_tool_call_pairing(msgs)
    tool_ids = [m["tool_call_id"] for m in out if m.get("role") == "tool"]
    assert tool_ids == ["c1", "c2"]
    assert "缺少执行结果" in out[-1]["content"]


def test_sanitize_drops_orphan_tool_messages():
    msgs = [
        {"role": "user", "content": "q"},
        {"role": "tool", "tool_call_id": "orphan", "content": "x"},
        {"role": "assistant", "content": "a"},
    ]
    out = sanitize_tool_call_pairing(msgs)
    assert all(m.get("role") != "tool" for m in out)


def test_prepare_messages_for_deepseek_completes_pair_and_reasoning():
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "x", "arguments": "{}"},
                }
            ],
        }
    ]
    out = prepare_messages_for_deepseek(msgs)
    assert out[0]["reasoning_content"] == ""
    assert out[1]["role"] == "tool"
    assert out[1]["tool_call_id"] == "c1"


def test_route_after_execute_ends_at_max_rounds():
    assert (
        _route_after_execute_tools({"tool_rounds": 10, "messages": []}, max_tool_rounds=10)
        == END
    )
    assert (
        _route_after_execute_tools({"tool_rounds": 9, "messages": []}, max_tool_rounds=10)
        == "call_model"
    )

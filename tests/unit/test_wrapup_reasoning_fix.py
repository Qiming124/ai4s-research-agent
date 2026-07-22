# 历史消息回传 reasoning_content（Campaign 收尾用例已随 Supervisor 移除）

from __future__ import annotations

from shared.schemas import ChatMessage
from server.agents.base import GeneralAgent
from server.agents.subagent import SubAgent
from server.config import get_settings


def test_build_messages_includes_reasoning_content():
    agent = GeneralAgent(settings=get_settings())
    history = [
        ChatMessage(role="user", content="q1"),
        ChatMessage(
            role="assistant",
            content="a1",
            reasoning_content="think hard",
        ),
        ChatMessage(role="user", content="q2"),
        ChatMessage(role="assistant", content="a2"),  # 无 reasoning
    ]
    msgs = agent._build_messages(history, "q3", "sys")
    asst = [m for m in msgs if m["role"] == "assistant"]
    assert asst[0]["reasoning_content"] == "think hard"
    assert "reasoning_content" not in asst[1]


def test_subagent_build_messages_includes_reasoning():
    agent = SubAgent("general", settings=get_settings())
    history = [
        ChatMessage(role="assistant", content="hi", reasoning_content="r"),
    ]
    msgs = agent._build_messages(history, "next", "sys")
    assert msgs[1]["reasoning_content"] == "r"

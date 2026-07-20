# 历史消息回传 reasoning_content + 收尾提示拆分

from __future__ import annotations

from shared.schemas import ChatMessage
from server.agents.base import GeneralAgent
from server.agents.subagent import SubAgent
from server.config import get_settings
from server.graph.research_supervisor import _wrapup_user_prompt


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


def test_wrapup_prompt_returns_short_user_and_system_context():
    campaign = {
        "id": "c1",
        "title": "t",
        "status": "done",
        "current_stage": "complete",
        "stage_artifacts": {"S3_theory": {"summary": "定理已证"}},
        "gates": {},
        "assumptions": [],
    }
    user, system_extra = _wrapup_user_prompt("请收尾", campaign)
    assert "请收尾" in user or "收尾" in user
    assert "定理已证" in system_extra or "S3" in system_extra or "收尾模式" in system_extra
    # 用户句不应再塞整包上下文（避免 L1 膨胀）
    assert "【收尾模式】" not in user
    assert len(user) < 500

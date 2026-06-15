"""
基础单元测试（不调用真实 DeepSeek API）。

运行：pytest tests/ -v
"""

from __future__ import annotations

import pytest

from server.memory.session import SessionStore
from shared.schemas import ChatMessage, ChatRequest


def test_session_store_roundtrip() -> None:
    """会话存储：追加、读取、清空。"""
    store = SessionStore()
    sid = store.create_session_id()
    store.append_message(sid, ChatMessage(role="user", content="hello"))
    store.append_message(sid, ChatMessage(role="assistant", content="hi"))

    messages = store.get_messages(sid)
    assert len(messages) == 2
    assert messages[0].role == "user"

    store.clear_session(sid)
    assert store.get_messages(sid) == []


def test_chat_request_validation() -> None:
    """ChatRequest 拒绝空 message。"""
    with pytest.raises(Exception):
        ChatRequest(message="")

"""CLI payload 辅助函数测试。"""

from __future__ import annotations

from client.cli import build_chat_payload


def test_build_chat_payload_server_default() -> None:
    payload = build_chat_payload(
        "hi",
        "sid",
        mode="chat",
        max_history=None,
        history_summary="default",
    )
    assert payload == {"message": "hi", "session_id": "sid", "mode": "chat"}


def test_build_chat_payload_with_overrides() -> None:
    payload = build_chat_payload(
        "hi",
        "sid",
        mode="math",
        max_history=10,
        history_summary="on",
    )
    assert payload == {
        "message": "hi",
        "session_id": "sid",
        "mode": "math",
        "max_history_messages": 10,
        "enable_history_summary": True,
    }


def test_build_chat_payload_summary_off() -> None:
    payload = build_chat_payload(
        "hi",
        "sid",
        mode="chat",
        max_history=5,
        history_summary="off",
    )
    assert payload["enable_history_summary"] is False

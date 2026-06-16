"""
基础单元测试（不调用真实 DeepSeek API）。

运行：pytest tests/ -v
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from server.config import Settings, get_settings
from server.memory.session import (
    InMemorySessionStore,
    get_session_store,
    reset_session_store,
)
from server.memory.sqlite_store import SQLiteSessionStore
from shared.schemas import ChatMessage, ChatRequest


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator:
    """参数化 fixture：memory 与 sqlite 两种后端共用同一套断言。"""
    if request.param == "memory":
        yield InMemorySessionStore()
    else:
        db = tmp_path / "test.db"
        yield SQLiteSessionStore(db)


def test_session_store_roundtrip(store: InMemorySessionStore | SQLiteSessionStore) -> None:
    """会话存储：追加、读取、清空（memory + sqlite）。"""
    sid = store.create_session_id()
    store.append_message(sid, ChatMessage(role="user", content="hello"))
    store.append_message(sid, ChatMessage(role="assistant", content="hi"))

    messages = store.get_messages(sid)
    assert len(messages) == 2
    assert messages[0].role == "user"

    store.clear_session(sid)
    assert store.get_messages(sid) == []
    assert store.session_exists(sid)


def test_session_store_get_messages_is_copy(
    store: InMemorySessionStore | SQLiteSessionStore,
) -> None:
    """get_messages 返回副本，外部修改不影响内部状态。"""
    sid = store.create_session_id()
    store.append_message(sid, ChatMessage(role="user", content="hello"))

    messages = store.get_messages(sid)
    messages.append(ChatMessage(role="assistant", content="extra"))

    assert len(store.get_messages(sid)) == 1


def test_session_store_reasoning_content(
    store: InMemorySessionStore | SQLiteSessionStore,
) -> None:
    """assistant 消息的 reasoning_content 可持久化往返。"""
    sid = store.create_session_id()
    store.append_message(
        sid,
        ChatMessage(
            role="assistant",
            content="answer",
            reasoning_content="thinking process",
        ),
    )
    messages = store.get_messages(sid)
    assert len(messages) == 1
    assert messages[0].reasoning_content == "thinking process"


def test_session_store_delete_session(
    store: InMemorySessionStore | SQLiteSessionStore,
) -> None:
    """delete_session 完全移除会话；clear_session 仅清空消息。"""
    sid = store.create_session_id()
    store.append_message(sid, ChatMessage(role="user", content="hello"))

    assert store.delete_session(sid) is True
    assert store.session_exists(sid) is False

    sid2 = store.create_session_id()
    store.get_or_create(sid2)
    assert store.clear_session(sid2) is True
    assert store.session_exists(sid2) is True
    assert store.get_messages(sid2) == []


def test_sqlite_persistence_across_instances(tmp_path: Path) -> None:
    """核心验收：实例 A 写入 → 新实例 B 读取同一 db 文件。"""
    db = tmp_path / "persist.db"
    store_a = SQLiteSessionStore(db)
    sid = store_a.create_session_id()
    store_a.append_message(sid, ChatMessage(role="user", content="hello"))
    store_a.append_message(sid, ChatMessage(role="assistant", content="world"))

    store_b = SQLiteSessionStore(db)
    messages = store_b.get_messages(sid)
    assert len(messages) == 2
    assert messages[0].content == "hello"
    assert messages[1].content == "world"


def test_get_session_store_factory_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """factory 在 SESSION_STORE_BACKEND=memory 时返回 InMemorySessionStore。"""
    get_settings.cache_clear()
    reset_session_store()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "memory")

    store = get_session_store()
    assert isinstance(store, InMemorySessionStore)

    reset_session_store()
    get_settings.cache_clear()


def test_get_session_store_factory_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """factory 在 SESSION_STORE_BACKEND=sqlite 时返回 SQLiteSessionStore。"""
    get_settings.cache_clear()
    reset_session_store()
    db_path = tmp_path / "factory.db"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SESSION_DB_PATH", str(db_path))

    store = get_session_store()
    assert isinstance(store, SQLiteSessionStore)

    reset_session_store()
    get_settings.cache_clear()


def test_chat_request_validation() -> None:
    """ChatRequest 拒绝空 message。"""
    with pytest.raises(Exception):
        ChatRequest(message="")


def test_validate_session_store_backend() -> None:
    """Settings 拒绝非法 SESSION_STORE_BACKEND。"""
    with pytest.raises(ValueError, match="SESSION_STORE_BACKEND"):
        Settings(
            deepseek_api_key="sk-test-key",
            session_store_backend="redis",
        )

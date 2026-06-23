"""请求级可观测上下文（ContextVar）——跨协程传递 request_id / session_id / agent_name。

ContextVar 作用：
    每条 HTTP 请求在 asyncio 中可能被多个协程处理。
    ContextVar 是 asyncio 安全的多协程局部存储——每个协程有独立副本，
    不互相污染，适合传递 request-scoped metadata。

使用：
    from server.observability import set_session_id, get_session_id
    set_session_id("abc123")
    # ... 在后续日志中自动注入 session_id
"""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
_agent_name: ContextVar[str | None] = ContextVar("agent_name", default=None)


def set_request_id(value: str | None) -> None:
    """设置当前协程的 request_id。"""
    _request_id.set(value)


def get_request_id() -> str | None:
    """读取当前协程的 request_id。未设置返回 None。"""
    return _request_id.get()


def set_session_id(value: str | None) -> None:
    """设置当前协程的 session_id。"""
    _session_id.set(value)


def get_session_id() -> str | None:
    """读取当前协程的 session_id。"""
    return _session_id.get()


def set_agent_name(value: str | None) -> None:
    """设置当前协程的 agent_name。"""
    _agent_name.set(value)


def get_agent_name() -> str | None:
    """读取当前协程的 agent_name。"""
    return _agent_name.get()


def reset_observability_context() -> None:
    """清空全部 ContextVar（仅测试使用）。"""
    set_request_id(None)
    set_session_id(None)
    set_agent_name(None)

# 当前请求/Agent 运行时的 RAG 会话上下文（供 MCP 工具注入 session_id）。

from __future__ import annotations

from contextvars import ContextVar

_current_rag_session_id: ContextVar[str | None] = ContextVar(
    "current_rag_session_id",
    default=None,
)


def set_rag_session_id(session_id: str | None):
    """设置当前 RAG 会话 ID，返回 reset token。"""
    return _current_rag_session_id.set(session_id)


def reset_rag_session_id(token) -> None:
    _current_rag_session_id.reset(token)


def get_rag_session_id() -> str | None:
    return _current_rag_session_id.get()

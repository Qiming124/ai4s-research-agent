"""Request-scoped observability context (ContextVar)."""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
_agent_name: ContextVar[str | None] = ContextVar("agent_name", default=None)


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def set_session_id(value: str | None) -> None:
    _session_id.set(value)


def get_session_id() -> str | None:
    return _session_id.get()


def set_agent_name(value: str | None) -> None:
    _agent_name.set(value)


def get_agent_name() -> str | None:
    return _agent_name.get()


def reset_observability_context() -> None:
    """Clear context vars (tests only)."""
    set_request_id(None)
    set_session_id(None)
    set_agent_name(None)

"""Structured logging and token usage observability (Phase 6)."""

from typing import Any

from server.observability.context import (
    get_agent_name,
    get_request_id,
    get_session_id,
    reset_observability_context,
    set_agent_name,
    set_request_id,
    set_session_id,
)
from server.observability.structured import log_event
from server.observability.token_usage import get_token_usage_store, record_token_usage


def finalize_chat_turn(
    session_id: str,
    agent_name: str,
    usage: dict[str, Any] | None,
) -> None:
    set_session_id(session_id)
    set_agent_name(agent_name)
    record_token_usage(session_id, agent_name, usage)


__all__ = [
    "finalize_chat_turn",
    "get_agent_name",
    "get_request_id",
    "get_session_id",
    "log_event",
    "record_token_usage",
    "reset_observability_context",
    "set_agent_name",
    "set_request_id",
    "set_session_id",
    "get_token_usage_store",
]

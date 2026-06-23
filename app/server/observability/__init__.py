"""
可观测性包：结构化日志 + token 用量统计 + HTTP 请求追踪。

模块：
    context.py     — ContextVar: request_id / session_id / agent_name
    structured.py  — StructuredLogFormatter + log_event 便捷函数
    token_usage.py — TokenUsageStore: SQLite token 用量事件表
    middleware.py   — RequestContextMiddleware: 请求追踪 + X-Request-ID

入口函数：
    finalize_chat_turn(session_id, agent_name, usage)
    每个 chat turn 结束时调用，写入 token 用量并设置可观测上下文。
"""

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
    """
    完成一次 chat turn 的后处理：设置 context + 记录 token 用量。

    由 GeneralAgent.run / SubAgent.run 在产出 done chunk 后调用。

    参数:
        session_id: 当前会话 ID
        agent_name: 当前 Agent 名
        usage: DeepSeek API 返回的 usage 字典（可为 None）
    """
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

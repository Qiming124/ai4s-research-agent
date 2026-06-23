"""结构化 JSON 日志格式化器 + log_event 辅助函数。

StructuredLogFormatter：
    继承 logging.Formatter，每行输出一条 JSON。
    自动注入 ContextVar 中的 request_id / session_id / agent_name。
    异常发生时自动包含 exception 字段（含完整 traceback）。

log_event：
    便捷函数，在 logger.log 时自动附加 structured_fields extra 字典。
    StructuredLogFormatter 读取 extra 合并到 JSON payload。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from server.observability.context import get_agent_name, get_request_id, get_session_id


class StructuredLogFormatter(logging.Formatter):
    """
    结构化 JSON 日志格式化器。

    输出格式：
        {
            "timestamp": "2025-01-01T12:00:00+00:00",
            "level": "INFO",
            "logger": "server.api.chat",
            "message": "请求已处理",
            "request_id": "uuid",
            "session_id": "uuid",
            "agent_name": "general",
            "event": "http_request_complete",
            "latency_ms": 123.45
        }

    注入规则：
        - ContextVar 中的 request_id/session_id/agent_name 非空时才写入对应字段
        - log_record.structured_fields 若为 dict，合并到 payload
        - 若 log_record 含异常信息，追加 exception 字段
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 自动注入可观测上下文
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        session_id = get_session_id()
        if session_id:
            payload["session_id"] = session_id
        agent_name = get_agent_name()
        if agent_name:
            payload["agent_name"] = agent_name

        # 合并 structured_fields（来自 log_event 调用）
        extra = getattr(record, "structured_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)

        # 异常信息
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    tool_name: str | None = None,
    latency_ms: float | None = None,
    **fields: Any,
) -> None:
    """
    记录一条结构化日志事件。

    参数:
        logger: 日志器实例（通常为模块级 logger）
        event: 事件名称（如 "tool_call_complete"、"http_request_start"）
        level: 日志级别（默认 INFO）
        tool_name: 可选工具名
        latency_ms: 可选延迟（毫秒），自动四舍五入到两位小数
        **fields: 额外字段，合并到 structured_fields

    内部运作：
        通过 log_record.extra={"structured_fields": {...}} 传递结构化字段，
        StructuredLogFormatter.format 读取并合并到 JSON payload。
    """
    structured: dict[str, Any] = {"event": event}
    if tool_name:
        structured["tool_name"] = tool_name
    if latency_ms is not None:
        structured["latency_ms"] = round(latency_ms, 2)
    structured.update(fields)
    logger.log(level, event, extra={"structured_fields": structured})

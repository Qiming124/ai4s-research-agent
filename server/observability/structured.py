"""Structured JSON logging helpers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from server.observability.context import get_agent_name, get_request_id, get_session_id


class StructuredLogFormatter(logging.Formatter):
    """Emit one JSON object per log line with standard observability fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        session_id = get_session_id()
        if session_id:
            payload["session_id"] = session_id
        agent_name = get_agent_name()
        if agent_name:
            payload["agent_name"] = agent_name

        extra = getattr(record, "structured_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)

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
    """Log a structured event; merges context vars and explicit fields."""
    structured: dict[str, Any] = {"event": event}
    if tool_name:
        structured["tool_name"] = tool_name
    if latency_ms is not None:
        structured["latency_ms"] = round(latency_ms, 2)
    structured.update(fields)
    logger.log(level, event, extra={"structured_fields": structured})

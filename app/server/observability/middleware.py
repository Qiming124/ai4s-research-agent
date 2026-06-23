"""FastAPI middleware for request tracing and HTTP latency logging."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from server.observability.context import set_request_id
from server.observability.structured import log_event

logger = logging.getLogger("server.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign request_id, propagate X-Request-ID, log request latency."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        start = time.perf_counter()
        log_event(
            logger,
            "http_request_start",
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000
            log_event(
                logger,
                "http_request_error",
                level=logging.ERROR,
                method=request.method,
                path=request.url.path,
                status_code=500,
                latency_ms=latency_ms,
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            logger,
            "http_request_complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response

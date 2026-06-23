"""
FastAPI 中间件：请求追踪与 HTTP 延迟日志。

RequestContextMiddleware：
    - 为每个 HTTP 请求分配 request_id（优先读取 X-Request-ID header）
    - 设置 ContextVar（供 StructuredLogFormatter 自动注入）
    - 记录 request_start / request_complete / request_error 结构化日志
    - 在响应头中回传 X-Request-ID

架构位置：
    server/main.py → create_app → app.add_middleware(RequestContextMiddleware)
    在所有 API 路由之前执行
"""

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
    """
    HTTP 请求追踪中间件。

    功能：
        1. 分配 request_id（X-Request-ID header 或随机 UUID）
        2. 记录 request_start → 路由处理 → request_complete/error
        3. 延迟以毫秒计（latency_ms）
        4. 响应头回传 X-Request-ID
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 1. 分配 request_id：优先客户端传入，否则生成新 UUID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        start = time.perf_counter()

        # 2. 记录 request_start 日志
        log_event(
            logger,
            "http_request_start",
            method=request.method,
            path=request.url.path,
        )

        # 3. 执行路由处理（含异常捕获）
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
            raise  # 异常继续抛出，由 FastAPI error handler 处理

        # 4. 记录 request_complete 日志
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            logger,
            "http_request_complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        # 5. 响应头注入 X-Request-ID（客户端可追踪）
        response.headers["X-Request-ID"] = request_id
        return response

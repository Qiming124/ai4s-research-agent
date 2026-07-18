# 安全地从同步上下文运行协程（兼容已有 running event loop）。

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_coro_sync(coro: Coroutine[None, None, T]) -> T:
    """在同步函数中执行协程。

    - 无 running loop：``asyncio.run``
    - 已有 running loop（FastAPI）：线程池中新建 loop，避免嵌套冲突

    注意：依赖全局 MCP 单例的协程应在主事件循环上 ``await``，
    不要从 async 请求里经本函数间接调用。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()

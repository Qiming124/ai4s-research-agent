"""
FastAPI 应用入口。

职责：
    - 创建 FastAPI app 实例
    - 挂载路由、CORS
    - 启动时加载配置并打印摘要（API Key 脱敏）

启动方式：
    uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

类比 C++：
    类似 main() 中初始化 HTTP server、注册路由 handler、listen 端口。

Debug：
    - 启动报 ValidationError：.env 中 DEEPSEEK_API_KEY 未配置
    - 端口占用：修改 .env 中 PORT 或 uvicorn --port 参数
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.api.chat import router as chat_router
from server.config import get_settings, setup_logging

logger = logging.getLogger(__name__)

# 前端构建产物目录（npm run build 后生成）
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用生命周期钩子：启动时初始化，关闭时清理。

    FastAPI 的 lifespan 类似 C++ 中 server 构造/析构或 init/shutdown 回调。
    """
    settings = get_settings()
    setup_logging(settings)

    # 启动时打印配置摘要（API Key 脱敏，便于确认 .env 是否加载正确）
    logger.info("=" * 50)
    logger.info("AI4S Research Agent Server 启动")
    logger.info("  模型: %s", settings.model)
    logger.info("  推理强度: %s", settings.reasoning_effort)
    logger.info("  max_tokens: %d", settings.max_tokens)
    logger.info("  API Key: %s", settings.masked_api_key())
    logger.info("  Base URL: %s", settings.deepseek_base_url)
    logger.info("  日志级别: %s", settings.log_level)
    logger.info("=" * 50)

    yield

    logger.info("Server 关闭")


def create_app() -> FastAPI:
    """工厂函数：创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title="AI4S Research Agent",
        description="深度学习损失函数极小值理论 — 科研辅助多智能体系统 Phase 1",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS：允许 CLI 或未来 Web 前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)

    # 生产模式：托管 web/dist 静态资源（开发时用 Vite :5173 + proxy）
    if WEB_DIST.exists():
        assets_dir = WEB_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        async def serve_index() -> FileResponse:
            return FileResponse(WEB_DIST / "index.html")

    return app


# uvicorn 默认查找的 app 对象：uvicorn server.main:app
app = create_app()


if __name__ == "__main__":
    # 支持 python -m server.main 直接启动（开发便捷）
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )

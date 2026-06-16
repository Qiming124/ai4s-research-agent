# =============================================================================
# FastAPI 应用入口。
#
# 职责：
#     1. 创建 FastAPI app 实例
#     2. 挂载 chat_router（对话 API 路由）
#     3. 配置 CORS 中间件（允许跨域访问）
#     4. 生产模式托管 web/dist 静态文件
#     5. 应用生命周期：启动加载配置/打印摘要，关闭记录日志
#
# 启动：
#     uvicorn server.main:app --host 127.0.0.1 --port 8000       # 生产
#     uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 # 开发
#
# Debug：
#     - ValidationError → .env 未配置 DEEPSEEK_API_KEY
#     - Errno 98        → 端口被占用，换端口或先 kill 旧进程
# =============================================================================

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
    # 应用生命周期管理器。
    # yield 前 → 启动时执行（加载配置、设置日志、打印摘要）
    # yield 后 → 关闭时执行（记录日志）
    settings = get_settings()
    setup_logging(settings)

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
    # 创建并配置 FastAPI 应用（工厂函数）。
    # 返回完成以下配置的 app 实例：
    #     1. 应用元信息
    #     2. CORS 中间件（允许所有来源跨域）
    #     3. 挂载 chat_router
    #     4. 若 web/dist 存在则托管静态资源
    app = FastAPI(
        title="AI4S Research Agent",
        description="深度学习损失函数极小值理论 — 科研辅助多智能体系统 Phase 1",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS：Phase 1 不做精细鉴权，允许所有来源跨域访问 API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载 API 路由（/health /v1/chat /v1/chat/stream /v1/sessions/*）
    app.include_router(chat_router)

    # 生产模式：dist 存在时托管 web/dist 静态文件与首页。
    # 开发模式 dist 不存在则跳过（用 Vite :5173 + proxy）
    if WEB_DIST.exists():
        assets_dir = WEB_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        async def serve_index() -> FileResponse:
            return FileResponse(WEB_DIST / "index.html")

    return app


# uvicorn 导入模块时自动查找名为 "app" 的变量
app = create_app()


# python -m server.main 开发启动
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )

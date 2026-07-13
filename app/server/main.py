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

from server.api.agents import router as agents_router
from server.api.chat import router as chat_router
from server.api.documents import router as documents_router
from server.api.mcp import router as mcp_router
from server.api.stats import router as stats_router
from server.api.export import router as export_router
from server.api.experiments import router as experiments_router
from server.api.jupyter import router as jupyter_router
from server.api.observability import router as observability_router
from server.api.campaigns import router as campaigns_router
from server.api.projects import router as projects_router
from server.api.sync import router as sync_router
from server.api.structured_memory import router as structured_memory_router
from server.api.theory import router as theory_router
from server.api.verification import router as verification_router
from server.config import get_settings, setup_logging
from server.mcp.client import get_mcp_client, reset_mcp_client
from server.observability.middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)

# 前端构建产物：app/web/dist
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用生命周期：启动时加载配置、连接 MCP/RAG；关闭时释放 MCP Client。

    参数:
        app: FastAPI 应用实例

    产出:
        无（yield 前后分别执行启动与清理逻辑）
    """
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
    if settings.session_store_backend == "sqlite":
        logger.info("  会话存储: sqlite (%s)", settings.session_db_path)
    else:
        logger.info("  会话存储: memory（重启后会话丢失）")
    if settings.enable_mcp:
        logger.info("  MCP: 已启用 (%s)", settings.mcp_config_path)
        from server.mcp.config import sync_mcp_runtime_env

        sync_mcp_runtime_env(settings)
        import os

        if not settings.tavily_api_key and not os.environ.get("TAVILY_API_KEY"):
            logger.warning(
                "未配置 TAVILY_API_KEY：web_search MCP 将尝试 DuckDuckGo/Wikipedia，"
                "国内网络通常超时；请在 conf/.env 设置 TAVILY_API_KEY（https://tavily.com）"
            )
        await get_mcp_client()
    else:
        logger.info("  MCP: 未启用")
    if settings.enable_rag:
        logger.info("  RAG: 已启用 (%s)，按 session_id 隔离", settings.rag_chroma_path)
    else:
        logger.info("  RAG: 未启用")
    if settings.global_memory_sync:
        from server.memory.structured.graph import sync_workspace_to_l4

        synced = sync_workspace_to_l4(settings)
        if synced:
            logger.info("  L4 全局记忆: 已同步 %d 条引理", synced)
    from server.memory.projects import get_project_store
    from server.memory.campaigns import get_campaign_store

    get_project_store()
    logger.info("  课题存储: 已初始化（含默认课题与任务看板）")
    get_campaign_store()
    logger.info("  Campaign 存储: 已初始化（含 PL 临界点示范 Campaign）")
    logger.info("=" * 50)

    yield

    if settings.enable_mcp:
        from server.mcp.client import _mcp_client

        if _mcp_client is not None:
            await _mcp_client.close()
        reset_mcp_client()
    logger.info("Server 关闭")


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用：注册路由、CORS、可观测中间件与静态资源托管。

    返回:
        配置完成的 FastAPI 实例
    """
    app = FastAPI(
        title="AI4S Research Agent",
        description="深度学习损失函数极小值理论 — 科研辅助多智能体系统 Phase 2A/2B",
        version="0.3.0",
        lifespan=lifespan,
    )

    # CORS：Phase 1 不做精细鉴权，允许所有来源跨域访问 API
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载 API 路由（/health /v1/chat /v1/chat/stream /v1/sessions/*）
    app.include_router(chat_router)
    app.include_router(agents_router)
    app.include_router(mcp_router)
    app.include_router(documents_router)
    app.include_router(stats_router)
    app.include_router(structured_memory_router)
    app.include_router(theory_router)
    app.include_router(experiments_router)
    app.include_router(export_router)
    app.include_router(projects_router)
    app.include_router(campaigns_router)
    app.include_router(verification_router)
    app.include_router(observability_router)
    app.include_router(sync_router)
    app.include_router(jupyter_router)

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

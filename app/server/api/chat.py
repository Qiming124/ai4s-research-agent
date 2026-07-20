# =============================================================================
# Chat API 路由模块。
#
# 职责：暴露所有对话相关的 HTTP 端点——这是外部与系统交互的唯一入口。
#       不做业务逻辑，只做：参数校验 → 调 Agent → 序列化响应。
#
# 架构位置：
#     server/main.py 通过 include_router 挂载本模块
#     本模块调用 GeneralAgent（业务层）与 SessionStore（会话层）
#
# 端点一览：
#     GET  /health                          — 健康检查
#     POST /v1/chat                         — 非流式对话
#     POST /v1/chat/stream                  — 流式对话（SSE）
#     GET  /v1/sessions                     — 会话列表
#     GET  /v1/sessions/{session_id}        — 查询会话历史
#     DELETE /v1/sessions/{session_id}      — 清空/删除会话
#
# SSE 说明：基于 HTTP 的单向推送（服务端→客户端），每条事件格式 data: {json}\n\n
#           FastAPI 用 StreamingResponse 把 async generator 转成 text/event-stream。
#
# Debug：
#     - 422 → 请求 JSON 不符合 ChatRequest schema
#     - 502 → DeepSeek API 调用失败，查看服务端日志
#     - SSE 收不到数据 → 确认 Content-Type 为 text/event-stream 且 Nginx 未缓冲
# =============================================================================

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from server.agents.base import get_general_agent
from server.agents.orchestrator import get_multi_agent_orchestrator
from server.config import get_settings
from server.memory.session import get_session_store
from shared.schemas import ChatRequest, ChatResponse, HealthResponse, SessionListResponse, SessionResponse, SessionSummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _effective_cot_mode(request: ChatRequest) -> str:
    """Math 模式默认使用 strict 思维链。"""
    if request.mode == "math" and request.cot_mode == "standard":
        return "strict"
    return request.cot_mode


# ── 健康检查 ─────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check() -> HealthResponse:
    """
    健康检查：确认服务已启动且配置已加载（不调用 LLM）。

    返回:
        HealthResponse: status、model、reasoning_effort
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )


# ── 非流式对话 ───────────────────────────────────────────────

def _use_multi_agent_orchestrator() -> bool:
    return get_settings().orchestration_backend == "langgraph"


@router.post("/v1/chat", response_model=ChatResponse, summary="非流式对话")
async def chat(request: ChatRequest) -> ChatResponse:
    """
    非流式对话：等待模型完整响应后一次返回 JSON。

    参数:
        request: ChatRequest，必填 message，可选 session_id、mode、MCP 等

    返回:
        ChatResponse: session_id、content、reasoning、usage

    异常:
        HTTPException 502: LLM 或编排层调用失败
    """
    try:
        if _use_multi_agent_orchestrator():
            orchestrator = get_multi_agent_orchestrator()
            session_id, content, reasoning, usage, _, _ = await orchestrator.run_sync(
                message=request.message,
                session_id=request.session_id,
                agent=request.agent,
                auto_route=request.auto_route,
                mode=request.mode,
                system_prompt_override=request.system_prompt,
                max_history_messages=request.max_history_messages,
                enable_history_summary=request.enable_history_summary,
                enable_tools=request.enable_tools,
                enable_thinking=request.enable_thinking,
                reasoning_effort=request.reasoning_effort,
                cot_mode=_effective_cot_mode(request),
                project_id=request.project_id,
                campaign_id=request.campaign_id,
            )
        else:
            agent = get_general_agent(math_mode=(request.mode == "math"))
            session_id, content, reasoning, usage = await agent.run_sync(
                message=request.message,
                session_id=request.session_id,
                system_prompt_override=request.system_prompt,
                max_history_messages=request.max_history_messages,
                enable_history_summary=request.enable_history_summary,
                enable_tools=request.enable_tools,
                enable_thinking=request.enable_thinking,
                reasoning_effort=request.reasoning_effort,
                cot_mode=_effective_cot_mode(request),
                project_id=request.project_id,
                campaign_id=request.campaign_id,
            )
    except Exception as exc:
        logger.exception("非流式对话失败")
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}") from exc

    return ChatResponse(
        session_id=session_id,
        content=content,
        reasoning=reasoning or None,
        usage=usage,
    )


# ── SSE 工具函数 ─────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    # 将 Python 字典序列化为 SSE 协议的事件字符串。
    # 格式："data: {json}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_generator(request: ChatRequest) -> AsyncIterator[str]:
    # 将 Agent 的 StreamChunk 转成 SSE 事件字符串流。
    #
    # 流程：
    #     1. 创建/获取 session_id
    #     2. 发送 meta 事件（携带 session_id）
    #     3. 调用 Agent.run() 逐块产出 reasoning/content/done/error
    #     4. 每个 StreamChunk 转一条 SSE data 事件
    session_store = get_session_store()
    session_id = session_store.get_or_create(request.session_id)

    if _use_multi_agent_orchestrator():
        orchestrator = get_multi_agent_orchestrator()
        target, route_reason = await orchestrator.resolve_target_agent(
            request.message,
            agent=request.agent,
            auto_route=request.auto_route,
            mode=request.mode,
        )
        yield _sse_event({
            "type": "meta",
            "session_id": session_id,
            "agent_name": target,
            "route_reason": route_reason,
        })

        try:
            async for chunk in orchestrator.run(
                message=request.message,
                session_id=session_id,
                agent=request.agent,
                auto_route=request.auto_route,
                mode=request.mode,
                system_prompt_override=request.system_prompt,
                max_history_messages=request.max_history_messages,
                enable_history_summary=request.enable_history_summary,
                enable_tools=request.enable_tools,
                enable_thinking=request.enable_thinking,
                reasoning_effort=request.reasoning_effort,
                cot_mode=_effective_cot_mode(request),
                project_id=request.project_id,
                campaign_id=request.campaign_id,
            ):
                payload = chunk.model_dump()
                yield _sse_event(payload)
        except Exception as exc:
            logger.exception("流式对话失败")
            yield _sse_event({"type": "error", "content": str(exc)})
        return

    agent = get_general_agent(math_mode=(request.mode == "math"))
    yield _sse_event({
        "type": "meta",
        "session_id": session_id,
        "agent_name": agent.name,
    })

    try:
        async for chunk in agent.run(
            message=request.message,
            session_id=session_id,
            system_prompt_override=request.system_prompt,
            max_history_messages=request.max_history_messages,
            enable_history_summary=request.enable_history_summary,
            enable_tools=request.enable_tools,
            enable_thinking=request.enable_thinking,
            reasoning_effort=request.reasoning_effort,
            cot_mode=_effective_cot_mode(request),
        ):
            payload = chunk.model_dump()
            yield _sse_event(payload)
    except Exception as exc:
        logger.exception("流式对话失败")
        yield _sse_event({"type": "error", "content": str(exc)})


# ── 流式对话（SSE） ──────────────────────────────────────────

@router.post("/v1/chat/stream", summary="SSE 流式对话")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    SSE 流式对话，事件类型见 StreamChunk.type。

    参数:
        request: 与非流式接口相同的 ChatRequest

    返回:
        StreamingResponse，media_type 为 text/event-stream
    """
    return StreamingResponse(
        _stream_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 会话管理 ─────────────────────────────────────────────────

@router.get("/v1/sessions", response_model=SessionListResponse, summary="会话列表")
async def list_sessions() -> SessionListResponse:
    """列出服务端已持久化的会话（SQLite 后端含 updated_at 与消息条数）。"""
    store = get_session_store()
    from server.memory.projects import get_project_store

    proj_store = get_project_store()
    if hasattr(store, "list_session_summaries"):
        raw = store.list_session_summaries()
        sessions = [
            SessionSummary(
                session_id=str(item["session_id"]),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                message_count=int(item.get("message_count", 0)),
                project_id=proj_store.get_project_for_session(str(item["session_id"])),
            )
            for item in raw
            if int(item.get("message_count", 0)) > 0
        ]
    else:
        sessions = [
            SessionSummary(
                session_id=sid,
                message_count=len(store.get_messages(sid)),
                project_id=proj_store.get_project_for_session(sid),
            )
            for sid in store.list_session_ids()
            if len(store.get_messages(sid)) > 0
        ]
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get(
    "/v1/sessions/{session_id}",
    response_model=SessionResponse,
    summary="查询会话历史",
)
async def get_session(
    session_id: str = Path(..., description="会话 ID", examples=["sess_demo"]),
) -> SessionResponse:
    """
    查询会话历史消息（含 reasoning、tool_calls）。

    参数:
        session_id: 会话 ID

    返回:
        SessionResponse

    异常:
        HTTPException 404: 会话不存在
    """
    store = get_session_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return SessionResponse(session_id=session_id, messages=store.get_messages(session_id))


@router.delete("/v1/sessions/{session_id}", summary="清空或删除会话")
async def delete_session(
    session_id: str = Path(..., description="会话 ID", examples=["sess_demo"]),
    purge: bool = Query(
        default=False,
        description="true=从存储中删除会话记录；false=仅清空消息（默认，供「清空会话」使用）",
        examples=[False],
    ),
) -> dict[str, str]:
    """
    会话删除或清空。

    - purge=false（默认）：清空消息，保留 session_id（顶栏「清空会话」、CLI /clear）
    - purge=true：删除会话记录（侧栏「×」移除会话）
    """
    store = get_session_store()
    settings = get_settings()
    if purge:
        existed = store.delete_session(session_id)
        if not existed:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        try:
            from server.memory.rag.session_refs import SessionRagRefStore
            from server.memory.rag.store import get_rag_store

            SessionRagRefStore(settings.session_db_path).clear_session(session_id)
            get_rag_store().clear_session_documents(session_id)
        except Exception:
            logger.exception("清除会话 RAG 数据失败 session_id=%s", session_id)
        return {"status": "deleted", "session_id": session_id}

    store.get_or_create(session_id)
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}

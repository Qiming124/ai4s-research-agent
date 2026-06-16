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
#     GET  /health                  — 健康检查
#     POST /v1/chat                 — 非流式对话
#     POST /v1/chat/stream          — 流式对话（SSE）
#     GET  /v1/sessions/{id}        — 查询会话历史
#     DELETE /v1/sessions/{id}      — 清空会话历史
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

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.agents.base import get_general_agent
from server.config import get_settings
from server.memory.session import get_session_store
from shared.schemas import ChatRequest, ChatResponse, HealthResponse, SessionResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ── 健康检查 ─────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    # 健康检查端点：确认服务已启动且配置加载正确。
    # 不调用 DeepSeek API，瞬间返回。
    # 返回示例：{"status":"ok","model":"deepseek-v4-pro","reasoning_effort":"max"}
    settings = get_settings()
    return HealthResponse(
        status="ok",
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )


# ── 非流式对话 ───────────────────────────────────────────────

@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    # 非流式对话端点：接收用户消息，等待模型完整响应后一次性返回 JSON。
    # 适合脚本调用、curl 测试、批量处理。
    #
    # 参数 request — ChatRequest（必填 message，可选 session_id / system_prompt）
    # 返回 ChatResponse JSON（session_id / content / reasoning / usage）
    agent = get_general_agent(math_mode=(request.mode == "math"))
    try:
        session_id, content, reasoning, usage = await agent.run_sync(
            message=request.message,
            session_id=request.session_id,
            system_prompt_override=request.system_prompt,
            max_history_messages=request.max_history_messages,
            enable_history_summary=request.enable_history_summary,
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
    agent = get_general_agent(math_mode=(request.mode == "math"))
    session_store = get_session_store()

    session_id = session_store.get_or_create(request.session_id)
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
        ):
            payload = chunk.model_dump()
            yield _sse_event(payload)
    except Exception as exc:
        logger.exception("流式对话失败")
        yield _sse_event({"type": "error", "content": str(exc)})


# ── 流式对话（SSE） ──────────────────────────────────────────

@router.post("/v1/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    # 流式对话端点，返回 SSE 事件流。
    #
    # 响应头：
    #     Content-Type: text/event-stream
    #     Cache-Control: no-cache        （禁用缓存）
    #     Connection: keep-alive         （保持连接）
    #     X-Accel-Buffering: no          （禁用 Nginx 缓冲）
    #
    # SSE 事件 type：
    #     meta      — 会话 ID
    #     reasoning — thinking 推理片段
    #     content   — 回答片段
    #     done      — 流结束，含 usage
    #     error     — 错误信息
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

@router.get("/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    # 查询指定会话的完整历史消息。
    # 返回 SessionResponse；404 表示 session_id 不存在。
    store = get_session_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return SessionResponse(session_id=session_id, messages=store.get_messages(session_id))


@router.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    # 清空指定会话的全部历史消息（保留会话 ID 本身）。
    # 若 session_id 不存在会自动创建后清空（幂等）。
    # CLI 的 /clear 命令调用此端点。
    store = get_session_store()
    store.get_or_create(session_id)
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}

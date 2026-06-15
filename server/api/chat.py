"""
Chat API 路由模块。

职责：
    暴露对话相关的 HTTP 端点，包括流式（SSE）与非流式 JSON 响应。

架构位置：
    server/main.py 挂载本 router
    本模块调用 GeneralAgent 与 SessionStore

SSE 说明（C++ 对照）：
    Server-Sent Events 是一种单向长连接推送协议，类似 WebSocket 但只有服务端→客户端。
    FastAPI 的 StreamingResponse 将 async generator 转为 text/event-stream 响应。
    每个事件格式：data: {json}\n\n

Debug：
    - 422：请求体不符合 ChatRequest schema
    - 500：DeepSeek API 或内部异常，查看服务端日志
    - SSE 客户端收不到数据：确认 Content-Type 为 text/event-stream
"""

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


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    健康检查端点。

    用途：确认服务已启动且配置已加载，不调用 DeepSeek API。
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    非流式对话端点。

    等待模型完整响应后一次性返回 JSON，适合脚本调用或 curl 测试。

    Debug curl 示例见 README.md
    """
    agent = get_general_agent()
    try:
        session_id, content, reasoning, usage = await agent.run_sync(
            message=request.message,
            session_id=request.session_id,
            system_prompt_override=request.system_prompt,
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


def _sse_event(data: dict) -> str:
    """
    将 dict 序列化为 SSE 事件字符串。

    SSE 规范要求每条消息以 "data: " 开头，以双换行结尾。
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_generator(request: ChatRequest) -> AsyncIterator[str]:
    """
    流式响应生成器：将 Agent 的 StreamChunk 转为 SSE 字符串。

    首个事件携带 session_id（在 Agent 处理过程中确定）。
    """
    agent = get_general_agent()
    session_store = get_session_store()
    # 预先创建/获取 session_id，以便在流开始前告知客户端
    session_id = session_store.get_or_create(request.session_id)

    # 发送 meta 事件，告知客户端 session_id
    yield _sse_event({"type": "meta", "session_id": session_id})

    try:
        async for chunk in agent.run(
            message=request.message,
            session_id=session_id,
            system_prompt_override=request.system_prompt,
        ):
            payload = chunk.model_dump()
            yield _sse_event(payload)
    except Exception as exc:
        logger.exception("流式对话失败")
        yield _sse_event({"type": "error", "content": str(exc)})


@router.post("/v1/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    流式对话端点（SSE）。

    响应 Content-Type: text/event-stream
    客户端应使用 httpx-sse 或类似库消费事件流。

    事件 type 说明：
        meta      — 会话 ID
        reasoning — thinking 推理片段
        content   — 回答片段
        done      — 流结束，含 usage
        error     — 错误信息
    """
    return StreamingResponse(
        _stream_generator(request),
        media_type="text/event-stream",
        headers={
            # 禁用 nginx 等反向代理的缓冲，确保 SSE 实时推送
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """
    查询指定会话的历史消息。

    Debug：
        404 表示该 session_id 从未被创建或已被 delete。
    """
    store = get_session_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return SessionResponse(session_id=session_id, messages=store.get_messages(session_id))


@router.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """
    重置会话：清空该 session_id 的全部历史消息。

    会话 ID 本身保留（若不存在则创建空会话），便于 CLI 固定 session 后反复 /clear。

    CLI 的 /clear 命令调用此端点。
    """
    store = get_session_store()
    store.get_or_create(session_id)
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}

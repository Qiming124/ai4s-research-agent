# =============================================================================
# 共享数据模型（Pydantic Schema）。
#
# 职责：定义 HTTP API 的请求体、响应体、流式 chunk 等数据结构。
#       每个字段在运行时自动校验类型与约束，不合法时 FastAPI 返回 422。
#
# 架构位置：
#     server/api/chat.py  ← 使用本文件的 ChatRequest / ChatResponse / StreamChunk
#     client/cli.py       ← 构造 ChatRequest 并发给服务端
#
# 主要依赖：pydantic.BaseModel — 自动 JSON 序列化/反序列化 + 类型校验。
#
# Debug：若 FastAPI 返回 422 → 请求 JSON 不符合此处定义的字段类型或约束。
# =============================================================================

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    # 单条对话消息，格式与 OpenAI Chat Completions API 保持一致。
    #
    # 字段：
    #     role    — "system"（系统提示）/ "user"（用户）/ "assistant"（模型回答）
    #     content — 文本内容，任意字符串

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    # POST /v1/chat 与 POST /v1/chat/stream 的请求体。
    #
    # 字段：
    #     message       — 用户本轮输入（必填，不能为空字符串）
    #     session_id    — 会话 ID。为空时服务端自动生成 UUID
    #     system_prompt — 可选：临时覆盖默认 system prompt
    #
    # Debug：message 为空字符串 → pydantic 校验失败返回 400/422。

    message: str = Field(..., min_length=1, description="用户输入的消息内容")
    session_id: str | None = Field(default=None, description="会话 ID，用于多轮对话上下文")
    system_prompt: str | None = Field(default=None, description="可选：覆盖默认 system prompt")


class ChatResponse(BaseModel):
    # POST /v1/chat（非流式）的响应体。
    #
    # 字段：
    #     session_id — 本条回答所属的会话 ID
    #     content    — 模型的最终回答文本（不含思考过程）
    #     reasoning  — 思考/推理过程文本。若 API 返回了 reasoning_content 则填充
    #     usage      — token 用量统计（prompt_tokens/completion_tokens/total_tokens）

    session_id: str
    content: str
    reasoning: str | None = None
    usage: dict[str, Any] | None = None


class StreamChunk(BaseModel):
    # 流式响应（SSE）中的单个数据块。
    # 每条 SSE 事件携带一个 StreamChunk 的 JSON，用 type 字段区分含义。
    #
    # 字段：
    #     type    — "reasoning"（思考片段）/ "content"（回答片段）/
    #               "done"（流结束）/ "error"（错误信息）
    #     content — type="reasoning"/"content"/"error" 时有效
    #     usage   — 仅 type="done" 时可能包含 token 统计

    type: Literal["reasoning", "content", "done", "error"]
    content: str = ""
    usage: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    # GET /v1/sessions/{id} 的响应体：返回指定会话的全部历史消息。
    #
    # 字段：
    #     session_id — 会话 ID
    #     messages   — 该会话下所有消息的列表（按时间顺序）

    session_id: str
    messages: list[ChatMessage]


class HealthResponse(BaseModel):
    # GET /health 的响应体：确认服务已启动且配置正确加载。
    #
    # 字段：
    #     status           — 固定 "ok"
    #     model            — 当前使用的模型 ID（如 deepseek-v4-pro）
    #     reasoning_effort — 当前推理强度（high 或 max）

    status: str
    model: str
    reasoning_effort: str

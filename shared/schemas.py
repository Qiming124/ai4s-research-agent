"""
共享数据模型（Pydantic Schema）。

职责：
    定义 HTTP API 的请求体、响应体、流式 chunk 等数据结构，并在运行时自动校验。

架构位置：
    server/api/chat.py  ← 使用 ChatRequest / ChatResponse
    client/cli.py       ← 构造 ChatRequest JSON

主要依赖：
    pydantic.BaseModel — 带类型校验的数据类，类似 C++ 中带 validator 的结构体 + JSON 序列化。

Debug：
    若 FastAPI 返回 422 Unprocessable Entity，说明请求 JSON 不符合此处定义的字段类型。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    单条对话消息，格式与 OpenAI Chat Completions API 一致。

    字段：
        role: "system" | "user" | "assistant" — 消息角色
        content: 文本内容

    类比 C++：
        struct ChatMessage { std::string role; std::string content; };
    """

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """
    POST /v1/chat 与 POST /v1/chat/stream 的请求体。

    字段：
        message: 用户本轮输入（必填）
        session_id: 会话 ID；为空时服务端自动生成 UUID
        system_prompt: 可选，覆盖默认系统提示词

    Debug：
        - message 不能为空字符串，否则服务端会返回 400
    """

    message: str = Field(..., min_length=1, description="用户输入的消息内容")
    session_id: str | None = Field(default=None, description="会话 ID，用于多轮对话上下文")
    system_prompt: str | None = Field(default=None, description="可选：覆盖默认 system prompt")


class ChatResponse(BaseModel):
    """
    POST /v1/chat 非流式响应体。

    字段：
        session_id: 本次对话所属的会话 ID
        content: 模型最终回答（不含 reasoning 过程）
        reasoning: 模型的 thinking/reasoning 过程（若 API 返回）
        usage: token 用量统计（若 API 返回）
    """

    session_id: str
    content: str
    reasoning: str | None = None
    usage: dict[str, Any] | None = None


class StreamChunk(BaseModel):
    """
    流式响应中的单个数据块。

    type 取值：
        "reasoning" — DeepSeek thinking 推理过程片段
        "content"   — 最终回答片段
        "done"      — 流结束，usage 字段可能携带 token 统计
        "error"     — 错误信息

    类比 C++：
        类似 std::variant 或 tagged union，用 type 字段区分 payload 含义。
    """

    type: Literal["reasoning", "content", "done", "error"]
    content: str = ""
    usage: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    """GET /v1/sessions/{id} 的响应体：返回某会话的全部历史消息。"""

    session_id: str
    messages: list[ChatMessage]


class HealthResponse(BaseModel):
    """GET /health 的响应体。"""

    status: str
    model: str
    reasoning_effort: str

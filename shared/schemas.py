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


class PersistedToolCall(BaseModel):
    # 持久化到会话中的单次 MCP 工具调用记录（Phase 3）。
    #
    # 字段与 SSE tool_call_* 事件对齐，供 Web 历史时间线回放。

    id: str = Field(description="tool_call_id")
    name: str = Field(description="qualified 工具名，如 filesystem__read_file")
    arguments: str = Field(default="", description="JSON 参数字符串")
    result: str | None = Field(default=None, description="工具返回内容（成功时）")
    status: Literal["success", "error"] = Field(default="success")
    error: str | None = Field(default=None, description="错误信息（status=error 时）")


class ChatMessage(BaseModel):
    # 单条对话消息，格式与 OpenAI Chat Completions API 保持一致。
    #
    # 字段：
    #     role    — "system"（系统提示）/ "user"（用户）/ "assistant"（模型回答）
    #     content — 文本内容，任意字符串

    role: Literal["system", "user", "assistant"]
    content: str
    reasoning_content: str | None = Field(
        default=None,
        description="assistant 消息的思考过程（Phase 2A 持久化）",
    )
    tool_calls: list[PersistedToolCall] | None = Field(
        default=None,
        description="assistant 消息关联的 MCP 工具调用记录（Phase 3 持久化）",
    )


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
    mode: Literal["chat", "math"] = Field(default="chat", description="对话模式：chat=通用，math=数学推导")
    max_history_messages: int | None = Field(
        default=None,
        ge=0,
        description="L1 保留最近 N 条历史；None 时使用服务端 .env 默认值",
    )
    enable_history_summary: bool | None = Field(
        default=None,
        description="截断时是否 LLM 摘要旧消息；None 时使用服务端 .env 默认值",
    )
    enable_tools: bool | None = Field(
        default=None,
        description="是否启用 MCP 工具；None 时使用服务端 ENABLE_MCP 默认值",
    )
    agent: Literal["general", "theory", "experiment", "literature"] | None = Field(
        default=None,
        description="指定 Agent；省略时按 auto_route 自动路由",
    )
    auto_route: bool = Field(
        default=True,
        description="未指定 agent 时是否自动意图路由；False 则使用 general",
    )


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
    #     type    — "reasoning" / "content" / "done" / "error" /
    #               "tool_call_start" / "tool_call_result" / "tool_call_error"
    #     content — 文本片段、工具参数 JSON 或工具返回结果
    #     usage   — 仅 type="done" 时可能包含 token 统计

    type: Literal[
        "reasoning",
        "content",
        "done",
        "error",
        "tool_call_start",
        "tool_call_result",
        "tool_call_error",
        "agent_handoff",
    ]
    content: str = ""
    usage: dict[str, Any] | None = None
    agent_name: str | None = Field(default=None, description="产出该 chunk 的 Agent 名称")
    tool_name: str | None = Field(default=None, description="MCP 工具名")
    tool_call_id: str | None = Field(default=None, description="工具调用 ID")
    a2a_task_id: str | None = Field(default=None, description="A2A 任务 ID（子任务追踪）")
    route_reason: str | None = Field(default=None, description="路由原因（meta/handoff）")
    from_agent: str | None = Field(default=None, description="handoff 来源 Agent")
    to_agent: str | None = Field(default=None, description="handoff 目标 Agent")


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


class MCPToolInfo(BaseModel):
    qualified_name: str
    tool_name: str
    description: str = ""


class MCPServerInfo(BaseModel):
    name: str
    enabled: bool = True
    connected: bool = False
    tools: list[MCPToolInfo] = Field(default_factory=list)


class MCPStatusResponse(BaseModel):
    server_enabled: bool = Field(description="服务端 ENABLE_MCP 配置")
    connected: bool = Field(description="MCP Client 是否已连接")
    servers: list[MCPServerInfo] = Field(default_factory=list)


class DocumentUploadRequest(BaseModel):
    """POST /v1/documents 请求体。"""

    content: str = Field(..., min_length=1, description="文档正文（markdown 或纯文本）")
    title: str | None = Field(default=None, description="文档标题")
    source: str = Field(default="", description="来源路径或 URL")
    doc_id: str | None = Field(default=None, description="可选：指定文档 ID（覆盖更新）")


class DocumentInfo(BaseModel):
    doc_id: str
    title: str
    source: str = ""
    chunk_count: int = 0
    created_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo] = Field(default_factory=list)
    total: int = 0


class DocumentUploadResponse(BaseModel):
    document: DocumentInfo
    status: str = "indexed"


class SessionRagRef(BaseModel):
    doc_id: str
    snippet: str = ""
    created_at: str | None = None


class SessionRagRefsResponse(BaseModel):
    session_id: str
    refs: list[SessionRagRef] = Field(default_factory=list)


class TokenUsageAgentBreakdown(BaseModel):
    agent_name: str
    event_count: int = 0
    total_tokens: int = 0


class TokenUsageTotals(BaseModel):
    event_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenUsageStatsResponse(BaseModel):
    filters: dict[str, str | None] = Field(default_factory=dict)
    totals: TokenUsageTotals
    by_agent: list[TokenUsageAgentBreakdown] = Field(default_factory=list)

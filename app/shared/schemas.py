# =============================================================================
# 共享数据模型（Pydantic Schema）。
#
# 职责：定义 HTTP API 的请求体、响应体、流式 chunk 等数据结构。
#       每个字段在运行时自动校验类型与约束，不合法时 FastAPI 返回 422。
#       Field(description/examples) 会进入 /openapi.json，供 Swagger UI 展示。
#
# 架构位置：
#     server/api/chat.py  ← ChatRequest / ChatResponse / StreamChunk
#     client/cli.py       ← 构造 ChatRequest
#     server/agents/      ← StreamChunk / PersistedToolCall
#     server/memory/      ← ChatMessage
#
# 依赖：pydantic.BaseModel — 自动 JSON 序列化/反序列化 + 类型校验。
#
# Debug：若 FastAPI 返回 422 → 请求 JSON 不符合字段类型或约束。
# =============================================================================

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── 核心对话模型 ─────────────────────────────────────────────

class PersistedToolCall(BaseModel):
    """
    持久化到会话中的 MCP 工具调用记录。

    与 SSE 事件 tool_call_start / tool_call_result / tool_call_error 对齐。
    写入 L2 会话的 messages 表中 assistant 消息的 tool_calls JSON 字段。
    """

    id: str = Field(
        description="tool_call_id，来自 DeepSeek API",
        examples=["call_abc123"],
    )
    name: str = Field(
        description="qualified 工具名，如 filesystem__read_file",
        examples=["filesystem__read_file"],
    )
    arguments: str = Field(
        default="",
        description="JSON 字符串格式的参数（非 dict，保证 DB 可存储）",
        examples=['{"path": "assumptions.md"}'],
    )
    result: str | None = Field(
        default=None,
        description="工具返回内容（成功时，可能被截断）",
        examples=["# Assumptions\n..."],
    )
    status: Literal["success", "error"] = Field(
        default="success",
        description="调用结果状态",
        examples=["success"],
    )
    error: str | None = Field(
        default=None,
        description="错误信息（status=error 时）",
        examples=[None],
    )


class ChatMessage(BaseModel):
    """
    单条对话消息，格式与 OpenAI Chat API 一致。

    比 OpenAI 标准格式多两个扩展字段：
        - reasoning_content: DeepSeek thinking 模式下的思考过程
        - tool_calls: MCP 工具调用记录（Phase 3 持久化）
    """

    role: Literal["system", "user", "assistant"] = Field(
        description="消息角色",
        examples=["user"],
    )
    content: str = Field(
        description="消息正文",
        examples=["请证明临界点附近的 Hessian 半正定条件"],
    )
    reasoning_content: str | None = Field(
        default=None,
        description="assistant 消息的思考过程（DeepSeek thinking 模式）",
        examples=["先回顾一阶必要条件…"],
    )
    tool_calls: list[PersistedToolCall] | None = Field(
        default=None,
        description="assistant 消息关联的 MCP 工具调用记录",
        examples=[None],
    )
    workflow_steps: list[dict[str, Any]] | None = Field(
        default=None,
        description="工作流时间线节点（plan/tool/verify/synthesize）",
        examples=[None],
    )


class ChatRequest(BaseModel):
    """
    POST /v1/chat 与 /v1/chat/stream 的请求体。

    字段：
        message: 用户输入（必填，至少 1 字符）
        session_id: 会话 ID，None 时服务端自动生成（UUID）
        system_prompt: 可选覆盖默认 system prompt
        mode: chat=通用对话 / math=数学推导（路由至 theory Agent）
        max_history_messages: L1 保留最近 N 条历史（None=服务端 .env 默认）
        enable_history_summary: 截断时是否 LLM 摘要（None=服务端 .env 默认）
        enable_tools: 是否启用 MCP 工具（None=服务端 .env 默认）
        agent: 指定 Agent（general/theory/experiment/literature/review/counterexample）
        auto_route: 未指定 agent 时是否自动意图路由
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "请用 SymPy 验证 Hessian 在临界点处半正定",
                    "session_id": "sess_demo",
                    "mode": "math",
                    "agent": "theory",
                    "auto_route": True,
                    "cot_mode": "strict",
                    "project_id": "default",
                    "enable_tools": True,
                }
            ]
        }
    )

    message: str = Field(
        ...,
        min_length=1,
        description="用户输入的消息内容",
        examples=["请用 SymPy 验证 Hessian 在临界点处半正定"],
    )
    session_id: str | None = Field(
        default=None,
        description="会话 ID，用于多轮对话上下文；省略时服务端自动生成",
        examples=["sess_demo"],
    )
    system_prompt: str | None = Field(
        default=None,
        description="可选：覆盖默认 system prompt",
        examples=["你是损失函数景观理论专家"],
    )
    mode: Literal["chat", "math"] = Field(
        default="chat",
        description="对话模式：chat=通用，math=数学推导",
        examples=["math"],
    )
    max_history_messages: int | None = Field(
        default=None,
        ge=0,
        description="L1 保留最近 N 条历史；None 为服务端默认值",
        examples=[20],
    )
    enable_history_summary: bool | None = Field(
        default=None,
        description="截断时是否 LLM 摘要旧消息；None 为服务端默认值",
        examples=[True],
    )
    enable_tools: bool | None = Field(
        default=None,
        description="是否启用 MCP 工具；None 为服务端 ENABLE_MCP 默认值",
        examples=[True],
    )
    agent: Literal["general", "theory", "experiment", "literature", "review", "counterexample"] | None = Field(
        default=None,
        description="指定 Agent；省略、null 或 auto 时按 auto_route 自动路由",
        examples=["theory"],
    )
    auto_route: bool = Field(
        default=True,
        description="未指定 agent 时是否自动意图路由；False 则固定 general",
        examples=[True],
    )

    @field_validator("agent", mode="before")
    @classmethod
    def _normalize_agent(cls, value: Any) -> Any:
        """API 实验室/旧客户端常误传 auto 或空串，视为未指定。"""
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in ("", "auto"):
            return None
        return value
    enable_thinking: bool | None = Field(
        default=None,
        description="是否启用 DeepSeek thinking（None=默认开启，仅影响最终回答）",
        examples=[True],
    )
    reasoning_effort: Literal["high", "max"] | None = Field(
        default=None,
        description="推理强度覆盖；None 为服务端 REASONING_EFFORT 默认",
        examples=["high"],
    )
    cot_mode: Literal["off", "standard", "strict"] = Field(
        default="standard",
        description="结构化思维链模式：off=关闭，standard=三节，strict=强制 Markdown 小节",
        examples=["strict"],
    )
    project_id: str | None = Field(
        default=None,
        description="关联课题 ID；省略时从 session 解析或回退 default",
        examples=["default"],
    )
    artifact_ids: list[str] | None = Field(
        default=None,
        description="注入上下文的工件 ID 列表（MethodCard / ExperimentPlan 等）",
        examples=[["art_method_1"]],
    )


class ChatResponse(BaseModel):
    """
    POST /v1/chat（非流式）的响应体。

    字段：
        session_id: 本条回答所属会话 ID
        content: 模型最终回答文本（不含思考过程）
        reasoning: 思考/推理过程文本（API 未返回 reasoning_content 时为 None）
        usage: token 用量统计（prompt_tokens/completion_tokens/total_tokens）
    """

    session_id: str = Field(
        description="本条回答所属会话 ID",
        examples=["sess_demo"],
    )
    content: str = Field(
        description="模型最终回答文本（不含思考过程）",
        examples=["在临界点处，若 Hessian 半正定则为一阶局部极小…"],
    )
    reasoning: str | None = Field(
        default=None,
        description="思考/推理过程文本；API 未返回时为 null",
        examples=["先写出梯度为零的条件…"],
    )
    usage: dict[str, Any] | None = Field(
        default=None,
        description="token 用量：prompt_tokens / completion_tokens / total_tokens",
        examples=[{"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}],
    )


class StreamChunk(BaseModel):
    """
    流式响应（SSE）中的单个数据块。

    每条 SSE 事件携带一个 StreamChunk 的 JSON，用 type 字段区分含义。

    事件类型：
        "reasoning"       — DeepSeek 思考/推理片段（灰色/折叠显示）
        "content"         — 最终回答文本片段（逐字流式）
        "done"            — 流结束（usage 可能包含 token 统计）
        "error"           — 发生异常（content 为错误描述）
        "tool_call_start"  — MCP 工具调用开始（content 为参数 JSON）
        "tool_call_result" — 工具调用成功返回（content 为结果文本）
        "tool_call_error"  — 工具调用失败（content 为错误信息）
        "agent_handoff"    — 多 Agent 路由切换（from_agent → to_agent）
        "verification_result" — 理论推导 SymPy 验证结果（JSON）

    元数据字段（仅在特定事件类型中填充）：
        agent_name: 产出该 chunk 的 Agent 名称
        tool_name: MCP 工具名（qualified）
        tool_call_id: 工具调用 ID
        a2a_task_id: A2A 子任务追踪 ID
        route_reason: 路由原因（如 "keyword:literature"）
        from_agent / to_agent: handoff 来源/目标 Agent
    """

    type: Literal[
        "reasoning",
        "content",
        "done",
        "error",
        "tool_call_start",
        "tool_call_result",
        "tool_call_error",
        "agent_handoff",
        "verification_result",
        "numerical_verification_result",
        "pipeline_stage",
        "pipeline_gate",
        "artifact_saved",
        "memory_warning",
        "cot_step",
        "workflow_step",
    ] = Field(
        description="SSE 事件类型",
        examples=["content"],
    )
    content: str = Field(
        default="",
        description="事件载荷文本（随 type 含义不同）",
        examples=["因此局部极小成立。"],
    )
    usage: dict[str, Any] | None = Field(
        default=None,
        description="仅 done 等事件可能携带 token 统计",
        examples=[None],
    )
    agent_name: str | None = Field(
        default=None,
        description="产出该 chunk 的 Agent 名",
        examples=["theory"],
    )
    tool_name: str | None = Field(
        default=None,
        description="MCP 工具名（qualified）",
        examples=["sympy__simplify"],
    )
    tool_call_id: str | None = Field(
        default=None,
        description="工具调用 ID",
        examples=["call_abc123"],
    )
    a2a_task_id: str | None = Field(
        default=None,
        description="A2A 子任务追踪 ID",
        examples=["task_01"],
    )
    route_reason: str | None = Field(
        default=None,
        description="路由原因（meta/handoff）",
        examples=["keyword:theory"],
    )
    from_agent: str | None = Field(
        default=None,
        description="handoff 来源 Agent",
        examples=["general"],
    )
    to_agent: str | None = Field(
        default=None,
        description="handoff 目标 Agent",
        examples=["theory"],
    )
    step_kind: Literal["plan", "tool", "verify", "synthesize"] | None = Field(
        default=None,
        description="workflow_step 节点类型",
        examples=["verify"],
    )
    status: Literal["running", "done", "pass", "fail", "skipped", "error"] | None = Field(
        default=None,
        description="workflow_step / verification 状态",
        examples=["pass"],
    )
    title: str | None = Field(
        default=None,
        description="workflow_step 标题",
        examples=["SymPy 验证"],
    )
    detail: str | None = Field(
        default=None,
        description="workflow_step 详情",
        examples=["eigenvalues >= 0"],
    )


# ── 会话管理 ─────────────────────────────────────────────────

class SessionResponse(BaseModel):
    """GET /v1/sessions/{id} 的响应体：返回指定会话的全部历史消息。"""

    session_id: str = Field(description="会话 ID", examples=["sess_demo"])
    messages: list[ChatMessage] = Field(
        description="按时间顺序的历史消息列表",
        examples=[[{"role": "user", "content": "你好"}]],
    )


class SessionSummary(BaseModel):
    """会话列表项：含时间与消息条数。"""

    session_id: str = Field(description="会话 ID", examples=["sess_demo"])
    created_at: str | None = Field(
        default=None,
        description="创建时间 ISO8601",
        examples=["2026-07-20T10:00:00"],
    )
    updated_at: str | None = Field(
        default=None,
        description="最近更新时间 ISO8601",
        examples=["2026-07-20T12:00:00"],
    )
    message_count: int = Field(
        default=0,
        description="消息条数",
        examples=[4],
    )
    project_id: str = Field(
        default="default",
        description="所属课题 ID",
        examples=["default"],
    )


class SessionListResponse(BaseModel):
    """GET /v1/sessions 响应。"""

    sessions: list[SessionSummary] = Field(
        default_factory=list,
        description="会话摘要列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="会话总数", examples=[1])


class AgentInfo(BaseModel):
    """单个 Agent 角色元数据。"""

    name: str = Field(description="Agent 标识", examples=["theory"])
    description: str = Field(
        default="",
        description="角色说明",
        examples=["理论推导与形式化证明"],
    )
    rag_enabled: bool = Field(
        default=False,
        description="是否默认启用 RAG",
        examples=[True],
    )
    default_tool_patterns: list[str] = Field(
        default_factory=list,
        description="默认 MCP 工具名通配白名单",
        examples=[["sympy__*", "rag__*"]],
    )


class AgentListResponse(BaseModel):
    """GET /v1/agents 响应。"""

    orchestration_backend: str = Field(
        description="编排后端：legacy 或 langgraph",
        examples=["langgraph"],
    )
    agents: list[AgentInfo] = Field(
        default_factory=list,
        description="可用 Agent 列表",
        examples=[[]],
    )


class HealthResponse(BaseModel):
    """GET /health 的响应体：确认服务已启动且配置正确加载。"""

    status: str = Field(description="服务状态，正常为 ok", examples=["ok"])
    model: str = Field(
        description="当前配置的模型 ID",
        examples=["deepseek-v4-flash"],
    )
    reasoning_effort: str = Field(
        description="当前默认推理强度",
        examples=["high"],
    )


# ── MCP 状态 ─────────────────────────────────────────────────

class MCPToolInfo(BaseModel):
    """单个 MCP 工具的描述信息。"""

    qualified_name: str = Field(
        description="qualified 工具名（server__tool）",
        examples=["filesystem__read_file"],
    )
    tool_name: str = Field(description="工具短名", examples=["read_file"])
    description: str = Field(
        default="",
        description="工具说明",
        examples=["读取工作区文件"],
    )


class MCPServerInfo(BaseModel):
    """单个 MCP Server 的连接状态与工具列表。"""

    name: str = Field(description="MCP Server 名", examples=["filesystem"])
    enabled: bool = Field(default=True, description="是否启用", examples=[True])
    connected: bool = Field(default=False, description="是否已连接", examples=[True])
    tools: list[MCPToolInfo] = Field(
        default_factory=list,
        description="该 Server 暴露的工具列表",
        examples=[[]],
    )


class MCPStatusResponse(BaseModel):
    """GET /v1/mcp/status 响应：服务端 MCP 开关与连接状态。"""

    server_enabled: bool = Field(
        description="服务端 ENABLE_MCP 配置",
        examples=[True],
    )
    connected: bool = Field(
        description="MCP Client 是否已连接",
        examples=[True],
    )
    servers: list[MCPServerInfo] = Field(
        default_factory=list,
        description="各 MCP Server 状态",
        examples=[[]],
    )


# ── RAG 文档 ─────────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    """POST /v1/documents 请求体：上传文档到课题共享 RAG（会话用于溯源）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "session_id": "sess_demo",
                    "project_id": "default",
                    "title": "Loss Landscape Notes",
                    "content": "# Critical points\n\nHessian PSD implies local min.",
                    "source": "notes/loss.md",
                }
            ]
        }
    )

    session_id: str = Field(
        ...,
        min_length=1,
        description="上传操作所属会话 ID",
        examples=["sess_demo"],
    )
    project_id: str | None = Field(
        default=None,
        description="课题 ID；缺省由会话反查",
        examples=["default"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="文档正文（markdown 或纯文本）",
        examples=["# Critical points\n\nHessian PSD implies local min."],
    )
    title: str | None = Field(
        default=None,
        description="文档标题",
        examples=["Loss Landscape Notes"],
    )
    source: str = Field(
        default="",
        description="来源路径或 URL",
        examples=["notes/loss.md"],
    )
    doc_id: str | None = Field(
        default=None,
        description="可选：指定文档 ID（覆盖更新）",
        examples=["doc_demo"],
    )


class DocumentInfo(BaseModel):
    """已索引文档的元数据。"""

    doc_id: str = Field(description="文档 ID", examples=["doc_demo"])
    session_id: str = Field(description="上传所属会话", examples=["sess_demo"])
    project_id: str = Field(
        default="default",
        description="所属课题",
        examples=["default"],
    )
    title: str = Field(description="文档标题", examples=["Loss Landscape Notes"])
    source: str = Field(default="", description="来源", examples=["notes/loss.md"])
    chunk_count: int = Field(default=0, description="切分 chunk 数", examples=[3])
    created_at: str = Field(
        description="创建时间 ISO8601",
        examples=["2026-07-20T10:00:00"],
    )


class DocumentListResponse(BaseModel):
    """GET /v1/documents 响应。"""

    documents: list[DocumentInfo] = Field(
        default_factory=list,
        description="文档列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="文档总数", examples=[1])


class DocumentUploadResponse(BaseModel):
    """POST /v1/documents 响应。"""

    document: DocumentInfo = Field(description="已索引文档元数据", examples=[None])
    status: str = Field(
        default="indexed",
        description="入库状态",
        examples=["indexed"],
    )


class SessionRagRef(BaseModel):
    """单条会话 RAG 引用：doc_id + 内容片段预览。"""

    doc_id: str = Field(description="被引用文档 ID", examples=["doc_demo"])
    snippet: str = Field(
        default="",
        description="检索片段预览",
        examples=["Hessian PSD implies local min."],
    )
    created_at: str | None = Field(
        default=None,
        description="引用时间",
        examples=["2026-07-20T11:00:00"],
    )


class SessionRagRefsResponse(BaseModel):
    """GET /v1/sessions/{id}/rag-refs 响应。"""

    session_id: str = Field(description="会话 ID", examples=["sess_demo"])
    refs: list[SessionRagRef] = Field(
        default_factory=list,
        description="RAG 引用列表",
        examples=[[]],
    )


# ── Token 用量统计 ───────────────────────────────────────────

class TokenUsageAgentBreakdown(BaseModel):
    """按 Agent 分组的 token 用量。"""

    agent_name: str = Field(description="Agent 名", examples=["theory"])
    event_count: int = Field(default=0, description="调用次数", examples=[5])
    total_tokens: int = Field(default=0, description="总 token 数", examples=[12000])


class TokenUsageTotals(BaseModel):
    """汇总 token 用量。"""

    event_count: int = Field(default=0, description="事件/调用总次数", examples=[10])
    prompt_tokens: int = Field(default=0, description="提示 token 合计", examples=[8000])
    completion_tokens: int = Field(
        default=0,
        description="生成 token 合计",
        examples=[4000],
    )
    total_tokens: int = Field(default=0, description="总 token", examples=[12000])


class TokenUsageStatsResponse(BaseModel):
    """GET /v1/stats/tokens 响应。"""

    filters: dict[str, str | None] = Field(
        default_factory=dict,
        description="本次查询使用的过滤条件",
        examples=[{"session_id": "sess_demo", "agent_name": None, "day": None}],
    )
    totals: TokenUsageTotals = Field(
        description="汇总用量",
        examples=[{"event_count": 10, "prompt_tokens": 8000, "completion_tokens": 4000, "total_tokens": 12000}],
    )
    by_agent: list[TokenUsageAgentBreakdown] = Field(
        default_factory=list,
        description="按 Agent 分解",
        examples=[[]],
    )


# ── L4 结构化科研记忆 ─────────────────────────────────────────

class StructuredMemoryEntry(BaseModel):
    """单条结构化记忆（定理、假设、实验结论、引用等）。"""

    id: int | None = Field(default=None, description="条目 ID", examples=[1])
    session_id: str | None = Field(
        default=None,
        description="所属会话；全局记忆可为 null",
        examples=["sess_demo"],
    )
    kind: Literal["theorem", "hypothesis", "conclusion", "citation", "note"] = Field(
        default="note",
        description="记忆类型",
        examples=["theorem"],
    )
    title: str = Field(
        default="",
        description="标题",
        examples=["局部极小充分条件"],
    )
    body: str = Field(
        ...,
        min_length=1,
        description="正文（Markdown/纯文本）",
        examples=["若 ∇f(x*)=0 且 ∇²f(x*) ≽ 0，则 x* 为一阶局部极小。"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="扩展元数据 JSON",
        examples=[{"symbols": ["x*", "f"]}],
    )
    created_at: str | None = Field(
        default=None,
        description="创建时间",
        examples=["2026-07-20T10:00:00"],
    )


class StructuredMemoryCreateRequest(BaseModel):
    """POST /v1/memory/structured 请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "session_id": "sess_demo",
                    "kind": "theorem",
                    "title": "局部极小充分条件",
                    "body": "若 ∇f(x*)=0 且 ∇²f(x*) ≽ 0，则 x* 为一阶局部极小。",
                    "metadata": {"source": "manual"},
                }
            ]
        }
    )

    session_id: str | None = Field(
        default=None,
        description="所属会话；省略则按全局/当前上下文写入",
        examples=["sess_demo"],
    )
    kind: Literal["theorem", "hypothesis", "conclusion", "citation", "note"] = Field(
        default="note",
        description="记忆类型",
        examples=["theorem"],
    )
    title: str = Field(
        default="",
        description="标题",
        examples=["局部极小充分条件"],
    )
    body: str = Field(
        ...,
        min_length=1,
        description="正文",
        examples=["若 ∇f(x*)=0 且 ∇²f(x*) ≽ 0，则 x* 为一阶局部极小。"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="扩展元数据",
        examples=[{"source": "manual"}],
    )


class StructuredMemoryUpdateRequest(BaseModel):
    """PATCH /v1/memory/structured/{id} 请求体（字段均可选）。"""

    kind: Literal["theorem", "hypothesis", "conclusion", "citation", "note"] | None = Field(
        default=None,
        description="记忆类型",
    )
    title: str | None = Field(default=None, description="标题")
    body: str | None = Field(default=None, min_length=1, description="正文")
    metadata: dict[str, Any] | None = Field(default=None, description="扩展元数据（整体替换）")


class StructuredMemoryImportCandidate(BaseModel):
    """PDF/Markdown 导入预览中的单条候选。"""

    kind: Literal["theorem", "hypothesis", "conclusion", "citation", "note"] = "theorem"
    title: str = ""
    body: str = ""
    page: int | None = None
    confidence: float = 0.5
    selected_default: bool = True


class StructuredMemoryMarkdownPreviewRequest(BaseModel):
    """POST /v1/memory/structured/preview-markdown 请求体。"""

    content: str = Field(..., min_length=1, description="含 ## 定理/引理 标题的 Markdown")


class StructuredMemoryImportPreviewResponse(BaseModel):
    """Markdown/文件导入预览响应。"""

    filename: str = ""
    text_chars: int = 0
    truncated: bool = False
    candidates: list[StructuredMemoryImportCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StructuredMemoryListResponse(BaseModel):
    """GET /v1/memory/structured 响应。"""

    entries: list[StructuredMemoryEntry] = Field(
        default_factory=list,
        description="记忆条目列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="条目总数", examples=[1])


class MemoryEdge(BaseModel):
    """知识图谱边。"""

    id: int | None = Field(default=None, description="边 ID", examples=[1])
    from_id: int = Field(description="起点条目 ID", examples=[1])
    to_id: int = Field(description="终点条目 ID", examples=[2])
    relation: Literal["depends_on", "contradicts", "supports", "cites"] = Field(
        default="depends_on",
        description="边关系类型",
        examples=["depends_on"],
    )
    created_at: str | None = Field(
        default=None,
        description="创建时间",
        examples=["2026-07-20T10:00:00"],
    )


class MemoryEdgeCreateRequest(BaseModel):
    """POST /v1/memory/structured/{id}/edges 请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"to_id": 2, "relation": "depends_on"}]
        }
    )

    to_id: int = Field(description="目标条目 ID", examples=[2])
    relation: Literal["depends_on", "contradicts", "supports", "cites"] = Field(
        default="depends_on",
        description="关系类型",
        examples=["depends_on"],
    )


class ExperimentRunInfo(BaseModel):
    """实验运行记录。"""

    run_id: str = Field(description="运行 ID", examples=["run_20260720_001"])
    name: str = Field(default="", description="实验名称", examples=["hessian_scan"])
    config_path: str = Field(
        default="",
        description="配置文件路径",
        examples=["configs/hessian_scan.yaml"],
    )
    status: str = Field(
        default="completed",
        description="状态：pending/running/completed/failed 等",
        examples=["completed"],
    )
    log_path: str = Field(
        default="",
        description="日志路径",
        examples=["logs/run_20260720_001.json"],
    )
    created_at: str | None = Field(
        default=None,
        description="创建时间",
        examples=["2026-07-20T10:00:00"],
    )
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="运行摘要 JSON",
        examples=[{"passed": True}],
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="指标 JSON",
        examples=[{"min_eigen": 0.01}],
    )


class ExperimentRunsResponse(BaseModel):
    """GET /v1/experiments/runs 响应。"""

    runs: list[ExperimentRunInfo] = Field(
        default_factory=list,
        description="实验运行列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="总数", examples=[1])


class LatexExportRequest(BaseModel):
    """POST /v1/export/* 请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "session_id": "sess_demo",
                    "title": "Loss Landscape Theory Notes",
                    "include_global": True,
                    "include_chat": True,
                    "project_id": "default",
                    "use_ai": False,
                    "ai_instructions": None,
                }
            ]
        }
    )

    session_id: str | None = Field(
        default=None,
        description="导出关联会话；省略则仅用课题/全局记忆",
        examples=["sess_demo"],
    )
    title: str = Field(
        default="Theory Export",
        description="导出文档标题",
        examples=["Loss Landscape Theory Notes"],
    )
    include_global: bool = Field(
        default=True,
        description="是否包含全局结构化记忆",
        examples=[True],
    )
    include_chat: bool = Field(
        default=True,
        description="是否包含会话对话内容",
        examples=[True],
    )
    project_id: str = Field(
        default="default",
        description="课题 ID",
        examples=["default"],
    )
    use_ai: bool = Field(
        default=False,
        description="是否用 LLM 润色草稿（polish / 部分导出）",
        examples=[False],
    )
    ai_instructions: str | None = Field(
        default=None,
        description="AI 润色额外指示（与前端预设共用）",
        examples=["写成 arXiv 短文风格，保留定理编号"],
    )


class ExportPolishResponse(BaseModel):
    """POST /v1/export/polish 响应。"""

    markdown: str = Field(
        description="润色后的 Markdown 草稿",
        examples=["# Theory Notes\n\n## Theorem 1\n..."],
    )
    ai_applied: bool = Field(
        default=False,
        description="是否实际调用了 LLM",
        examples=[True],
    )
    message: str = Field(
        default="",
        description="提示信息",
        examples=["已应用 AI 润色"],
    )


class ExportPreviewResponse(BaseModel):
    """GET /v1/export/preview 响应。"""

    entry_count: int = Field(default=0, description="可导出条目总数", examples=[5])
    session_structured_count: int = Field(
        default=0,
        description="会话结构化记忆条数",
        examples=[2],
    )
    global_structured_count: int = Field(
        default=0,
        description="全局结构化记忆条数",
        examples=[3],
    )
    chat_message_count: int = Field(
        default=0,
        description="会话消息条数",
        examples=[8],
    )
    source: str = Field(
        default="empty",
        description="预览数据来源标签",
        examples=["session+global"],
    )
    hint: str = Field(
        default="",
        description="给前端的提示文案",
        examples=["可导出 5 条记忆与 8 条对话"],
    )


class LatexExportResponse(BaseModel):
    """POST /v1/export/latex 响应。"""

    latex: str = Field(
        description="生成的 LaTeX 源码",
        examples=["\\documentclass{article}\n\\begin{document}\n..."],
    )
    path: str | None = Field(
        default=None,
        description="服务端落盘路径（若有）",
        examples=["data/exports/theory.tex"],
    )
    bib_path: str | None = Field(
        default=None,
        description="配套 .bib 路径（若有）",
        examples=["data/exports/refs.bib"],
    )


# ── 课题（Project）─────────────────────────────────────────────

class ProjectInfo(BaseModel):
    """课题详情。"""

    id: str = Field(description="课题 ID", examples=["default"])
    name: str = Field(description="课题名称", examples=["默认课题"])
    description: str = Field(
        default="",
        description="课题简介",
        examples=["损失函数极小值理论研究"],
    )
    created_by: str = Field(
        default="",
        description="创建者标识",
        examples=["alice"],
    )
    default_assumptions: list[str] = Field(
        default_factory=list,
        description="默认假设列表",
        examples=[["f 二阶连续可微"]],
    )
    workspace_path: str = Field(
        default="",
        description="理论工作区根路径",
        examples=["data/theory/default"],
    )
    rag_namespace: str = Field(
        default="",
        description="RAG 命名空间",
        examples=["project:default"],
    )
    created_at: str | None = Field(
        default=None,
        description="创建时间",
        examples=["2026-01-01T00:00:00"],
    )
    updated_at: str | None = Field(
        default=None,
        description="更新时间",
        examples=["2026-07-20T10:00:00"],
    )


class ProjectListResponse(BaseModel):
    """课题列表响应。"""

    projects: list[ProjectInfo] = Field(
        default_factory=list,
        description="课题列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="课题总数", examples=[1])


class ProjectCreateRequest(BaseModel):
    """创建课题请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Hessian 极小值课题",
                    "description": "研究深度网络损失景观临界点",
                    "created_by": "alice",
                }
            ]
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        description="课题名称",
        examples=["Hessian 极小值课题"],
    )
    description: str = Field(
        default="",
        description="课题简介",
        examples=["研究深度网络损失景观临界点"],
    )
    created_by: str = Field(
        default="",
        description="创建者",
        examples=["alice"],
    )


class ProjectUpdateRequest(BaseModel):
    """更新课题请求体（部分字段）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"name": "新名称", "description": "更新后的简介"}]
        }
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        description="新名称；省略则不改",
        examples=["新名称"],
    )
    description: str | None = Field(
        default=None,
        description="新简介；省略则不改",
        examples=["更新后的简介"],
    )


class ProjectMemberInfo(BaseModel):
    """课题成员。"""

    id: int = Field(description="成员记录 ID", examples=[1])
    project_id: str = Field(description="课题 ID", examples=["default"])
    user_id: str = Field(description="用户标识", examples=["alice"])
    role: Literal["pi", "theorist", "experimenter", "reviewer", "literature"] = Field(
        description="角色",
        examples=["theorist"],
    )
    created_at: str | None = Field(
        default=None,
        description="加入时间",
        examples=["2026-07-01T00:00:00"],
    )


class ProjectTaskInfo(BaseModel):
    """课题任务看板项。"""

    id: int = Field(description="任务 ID", examples=[1])
    project_id: str = Field(description="课题 ID", examples=["default"])
    title: str = Field(description="任务标题", examples=["形式化 Hessian 条件"])
    description: str = Field(
        default="",
        description="任务说明",
        examples=["写出假设与定理草稿"],
    )
    assignee_role: str = Field(
        default="theorist",
        description="指派角色",
        examples=["theorist"],
    )
    status: Literal["todo", "in_progress", "blocked", "done"] = Field(
        default="todo",
        description="任务状态",
        examples=["todo"],
    )
    related_entry_id: int | None = Field(
        default=None,
        description="关联结构化记忆条目 ID",
        examples=[1],
    )
    created_at: str | None = Field(
        default=None,
        description="创建时间",
        examples=["2026-07-20T10:00:00"],
    )
    updated_at: str | None = Field(
        default=None,
        description="更新时间",
        examples=["2026-07-20T12:00:00"],
    )


class ProjectTasksResponse(BaseModel):
    """任务列表响应。"""

    tasks: list[ProjectTaskInfo] = Field(
        default_factory=list,
        description="任务列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="任务总数", examples=[1])


class ProjectTaskCreateRequest(BaseModel):
    """创建任务请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "形式化 Hessian 条件",
                    "description": "写出假设与定理草稿",
                    "assignee_role": "theorist",
                    "related_entry_id": None,
                }
            ]
        }
    )

    title: str = Field(
        ...,
        min_length=1,
        description="任务标题",
        examples=["形式化 Hessian 条件"],
    )
    description: str = Field(
        default="",
        description="任务说明",
        examples=["写出假设与定理草稿"],
    )
    assignee_role: str = Field(
        default="theorist",
        description="指派角色",
        examples=["theorist"],
    )
    related_entry_id: int | None = Field(
        default=None,
        description="关联记忆条目 ID",
        examples=[None],
    )


class ProjectSessionInfo(BaseModel):
    """课题关联的会话。"""

    session_id: str = Field(description="会话 ID", examples=["sess_demo"])
    project_id: str = Field(description="课题 ID", examples=["default"])


class ProjectSessionsResponse(BaseModel):
    """课题会话列表响应。"""

    sessions: list[ProjectSessionInfo] = Field(
        default_factory=list,
        description="关联会话列表",
        examples=[[]],
    )
    total: int = Field(default=0, description="关联会话数", examples=[1])


# ── 验证账本 ──────────────────────────────────────────────────

class VerificationRecordInfo(BaseModel):
    """单条验证记录。"""

    id: int = Field(description="记录 ID", examples=[1])
    project_id: str = Field(
        default="default",
        description="课题 ID",
        examples=["default"],
    )
    session_id: str | None = Field(
        default=None,
        description="关联会话",
        examples=["sess_demo"],
    )
    entry_id: int | None = Field(
        default=None,
        description="关联结构化记忆条目",
        examples=[1],
    )
    claim_id: str = Field(
        default="",
        description="断言/claim 标识",
        examples=["claim_hessian_psd"],
    )
    tier: Literal["symbolic", "numerical", "experiment"] = Field(
        default="numerical",
        description="验证层级",
        examples=["symbolic"],
    )
    executor: str = Field(
        default="",
        description="执行器名",
        examples=["sympy"],
    )
    agent_name: str = Field(
        default="",
        description="触发 Agent",
        examples=["theory"],
    )
    passed: bool = Field(default=False, description="是否通过", examples=[True])
    result: dict[str, Any] = Field(
        default_factory=dict,
        description="验证结果 JSON",
        examples=[{"ok": True, "detail": "eigenvalues >= 0"}],
    )
    artifacts: list[str] = Field(
        default_factory=list,
        description="产物路径列表",
        examples=[["data/verify/claim_1.json"]],
    )
    created_at: str | None = Field(
        default=None,
        description="创建时间",
        examples=["2026-07-20T10:00:00"],
    )


class VerificationRecordsResponse(BaseModel):
    """验证记录列表响应。"""

    records: list[VerificationRecordInfo] = Field(
        default_factory=list,
        description="验证记录",
        examples=[[]],
    )
    total: int = Field(default=0, description="总数", examples=[1])


class VerificationDashboardResponse(BaseModel):
    """验证仪表盘汇总。"""

    project_id: str = Field(
        default="default",
        description="课题 ID",
        examples=["default"],
    )
    total_records: int = Field(default=0, description="记录总数", examples=[10])
    passed: int = Field(default=0, description="通过数", examples=[8])
    failed: int = Field(default=0, description="失败数", examples=[2])
    by_tier: dict[str, int] = Field(
        default_factory=dict,
        description="按验证层级统计",
        examples=[{"symbolic": 5, "numerical": 4, "experiment": 1}],
    )
    recent: list[VerificationRecordInfo] = Field(
        default_factory=list,
        description="最近若干条记录",
        examples=[[]],
    )


class VerificationClaimRequest(BaseModel):
    """POST /v1/verification/run 请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "claim": {
                        "id": "claim_hessian_psd",
                        "kind": "symbolic",
                        "expression": "H.eigenvals()",
                    },
                    "session_id": "sess_demo",
                    "project_id": "default",
                    "entry_id": 1,
                    "persist": True,
                }
            ]
        }
    )

    claim: dict[str, Any] = Field(
        description="待验证断言对象（结构随执行器而定）",
        examples=[{"id": "claim_hessian_psd", "kind": "symbolic"}],
    )
    session_id: str | None = Field(
        default=None,
        description="关联会话",
        examples=["sess_demo"],
    )
    project_id: str = Field(
        default="default",
        description="课题 ID",
        examples=["default"],
    )
    entry_id: int | None = Field(
        default=None,
        description="关联记忆条目",
        examples=[1],
    )
    persist: bool = Field(
        default=True,
        description="是否写入验证账本",
        examples=[True],
    )


class ExperimentRunRequest(BaseModel):
    """触发实验运行请求体。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "config_path": "configs/hessian_scan.yaml",
                    "session_id": "sess_demo",
                }
            ]
        }
    )

    config_path: str = Field(
        ...,
        min_length=1,
        description="实验配置文件相对路径",
        examples=["configs/hessian_scan.yaml"],
    )
    session_id: str | None = Field(
        default=None,
        description="关联会话（用于溯源）",
        examples=["sess_demo"],
    )


# ── 可观测性 ───────────────────────────────────────────

class ObservabilitySummary(BaseModel):
    """可观测摘要。"""

    project_id: str = Field(
        default="default",
        description="课题 ID",
        examples=["default"],
    )
    verification_total: int = Field(
        default=0,
        description="验证记录总数",
        examples=[10],
    )
    verification_passed: int = Field(
        default=0,
        description="验证通过数",
        examples=[8],
    )
    verification_pass_rate: float = Field(
        default=0.0,
        description="通过率 0~1",
        examples=[0.8],
    )
    by_agent: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="按 Agent 的调用/验证统计",
        examples=[{"theory": {"calls": 5, "passed": 4}}],
    )


class AgentQualityResponse(BaseModel):
    """Agent 质量面板。"""

    agents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="各 Agent 质量指标列表",
        examples=[[{"name": "theory", "pass_rate": 0.8, "calls": 5}]],
    )


# ── Jupyter 桥接 ──────────────────────────────────────────────

class NotebookResultUploadRequest(BaseModel):
    """Jupyter 结果回传请求。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "hessian_scan_nb",
                    "project_id": "default",
                    "session_id": "sess_demo",
                    "summary": {"passed": True},
                    "metrics": {"min_eigen": 0.01},
                }
            ]
        }
    )

    name: str = Field(
        default="notebook_result",
        description="结果名称",
        examples=["hessian_scan_nb"],
    )
    project_id: str = Field(
        default="default",
        description="课题 ID",
        examples=["default"],
    )
    session_id: str | None = Field(
        default=None,
        description="关联会话",
        examples=["sess_demo"],
    )
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="摘要 JSON",
        examples=[{"passed": True}],
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="指标 JSON",
        examples=[{"min_eigen": 0.01}],
    )


class NotebookResultUploadResponse(BaseModel):
    """Jupyter 结果回传响应。"""

    run_id: str = Field(description="写入的运行 ID", examples=["run_nb_001"])
    log_path: str = Field(
        description="落盘日志路径",
        examples=["data/experiments/logs/run_nb_001.json"],
    )
    status: str = Field(
        default="indexed",
        description="入库状态",
        examples=["indexed"],
    )


# ── 提示词优化 ──────────────────────────────────────────────


class PromptTemplateInfo(BaseModel):
    """科研提示词风格模板元数据。"""

    id: str = Field(description="风格 id", examples=["rccf"])
    name: str = Field(description="英文名", examples=["RCCF"])
    name_zh: str = Field(description="中文名", examples=["角色-上下文-约束-格式"])
    description: str = Field(description="风格说明")
    reference: str = Field(default="", description="参考来源")
    skeleton: str = Field(description="结构骨架")
    best_for: list[str] = Field(default_factory=list, description="适用场景")


class PromptTestCaseInfo(BaseModel):
    """提示词优化测试案例。"""

    id: str = Field(description="案例 id", examples=["loss_landscape"])
    title: str = Field(description="标题")
    category: str = Field(description="类别", examples=["theory"])
    raw_prompt: str = Field(description="原始提示词")
    context: str = Field(default="", description="补充语境")
    expected_traits: list[str] = Field(default_factory=list, description="期望特质")
    source_note: str = Field(default="", description="来源说明")


class PromptOptimizeRequest(BaseModel):
    """POST /v1/prompt/optimize 请求体。"""

    text: str = Field(..., min_length=1, description="待优化的原始提示词")
    context: str = Field(default="", description="补充语境")
    goal: str = Field(
        default="",
        description="优化目标，如更清晰、更可验证、适合 Math 模式",
    )
    mode: Literal["chat", "math"] = Field(default="chat", description="对话模式")
    agent: str | None = Field(default=None, description="目标 Agent")
    style_ids: list[str] | None = Field(
        default=None,
        description="指定风格 id 列表；默认生成全部四种",
    )


class PromptStyleVariant(BaseModel):
    """一种风格的优化结果。"""

    style_id: str
    style_name: str
    style_name_zh: str
    prompt: str
    scores: dict[str, int] = Field(default_factory=dict)
    total_score: int = 0
    highlights: list[str] = Field(default_factory=list)
    recommended: bool = False


class PromptOptimizeResponse(BaseModel):
    """提示词优化响应。"""

    original: str
    recommended_style_id: str
    recommended_prompt: str
    rationale: str = ""
    variants: list[PromptStyleVariant] = Field(default_factory=list)
    ai_applied: bool = False
    message: str = ""

# =============================================================================
# 共享数据模型（Pydantic Schema）。
#
# 职责：定义 HTTP API 的请求体、响应体、流式 chunk 等数据结构。
#       每个字段在运行时自动校验类型与约束，不合法时 FastAPI 返回 422。
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

from pydantic import BaseModel, Field


# ── 核心对话模型 ─────────────────────────────────────────────

class PersistedToolCall(BaseModel):
    """
    持久化到会话中的 MCP 工具调用记录。

    与 SSE 事件 tool_call_start / tool_call_result / tool_call_error 对齐。
    写入 L2 会话的 messages 表中 assistant 消息的 tool_calls JSON 字段。
    """

    id: str = Field(description="tool_call_id，来自 DeepSeek API")
    name: str = Field(
        description="qualified 工具名，如 filesystem__read_file"
    )
    arguments: str = Field(
        default="",
        description="JSON 字符串格式的参数（非 dict，保证 DB 可存储）",
    )
    result: str | None = Field(
        default=None,
        description="工具返回内容（成功时，可能被截断）",
    )
    status: Literal["success", "error"] = Field(default="success")
    error: str | None = Field(
        default=None,
        description="错误信息（status=error 时）",
    )


class ChatMessage(BaseModel):
    """
    单条对话消息，格式与 OpenAI Chat API 一致。

    比 OpenAI 标准格式多两个扩展字段：
        - reasoning_content: DeepSeek thinking 模式下的思考过程
        - tool_calls: MCP 工具调用记录（Phase 3 持久化）
    """

    role: Literal["system", "user", "assistant"]
    content: str
    reasoning_content: str | None = Field(
        default=None,
        description="assistant 消息的思考过程（DeepSeek thinking 模式）",
    )
    tool_calls: list[PersistedToolCall] | None = Field(
        default=None,
        description="assistant 消息关联的 MCP 工具调用记录",
    )
    workflow_steps: list[dict[str, Any]] | None = Field(
        default=None,
        description="工作流时间线节点（plan/tool/verify/synthesize）",
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

    message: str = Field(..., min_length=1, description="用户输入的消息内容")
    session_id: str | None = Field(default=None, description="会话 ID，用于多轮对话上下文")
    system_prompt: str | None = Field(default=None, description="可选：覆盖默认 system prompt")
    mode: Literal["chat", "math"] = Field(default="chat", description="对话模式：chat=通用，math=数学推导")
    max_history_messages: int | None = Field(
        default=None,
        ge=0,
        description="L1 保留最近 N 条历史；None 为服务端默认值",
    )
    enable_history_summary: bool | None = Field(
        default=None,
        description="截断时是否 LLM 摘要旧消息；None 为服务端默认值",
    )
    enable_tools: bool | None = Field(
        default=None,
        description="是否启用 MCP 工具；None 为服务端 ENABLE_MCP 默认值",
    )
    agent: Literal["general", "theory", "experiment", "literature", "review", "counterexample"] | None = Field(
        default=None,
        description="指定 Agent；省略时按 auto_route 自动路由",
    )
    auto_route: bool = Field(
        default=True,
        description="未指定 agent 时是否自动意图路由；False 则固定 general",
    )
    enable_thinking: bool | None = Field(
        default=None,
        description="是否启用 DeepSeek thinking（None=默认开启，仅影响最终回答）",
    )
    reasoning_effort: Literal["high", "max"] | None = Field(
        default=None,
        description="推理强度覆盖；None 为服务端 REASONING_EFFORT 默认",
    )
    cot_mode: Literal["off", "standard", "strict"] = Field(
        default="standard",
        description="结构化思维链模式：off=关闭，standard=三节，strict=强制 Markdown 小节",
    )
    project_id: str | None = Field(
        default=None,
        description="关联课题 ID；省略时从 session 解析或回退 default",
    )
    campaign_id: str | None = Field(
        default=None,
        description="关联科研 Campaign ID；省略时使用课题活跃 Campaign",
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

    session_id: str
    content: str
    reasoning: str | None = None
    usage: dict[str, Any] | None = None


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
        "campaign_update",
        "artifact_saved",
        "memory_warning",
        "cot_step",
        "workflow_step",
    ]
    content: str = ""
    usage: dict[str, Any] | None = None
    agent_name: str | None = Field(default=None, description="产出该 chunk 的 Agent 名")
    tool_name: str | None = Field(default=None, description="MCP 工具名（qualified）")
    tool_call_id: str | None = Field(default=None, description="工具调用 ID")
    a2a_task_id: str | None = Field(default=None, description="A2A 子任务追踪 ID")
    route_reason: str | None = Field(default=None, description="路由原因（meta/handoff）")
    from_agent: str | None = Field(default=None, description="handoff 来源 Agent")
    to_agent: str | None = Field(default=None, description="handoff 目标 Agent")
    step_kind: Literal["plan", "tool", "verify", "synthesize"] | None = Field(
        default=None,
        description="workflow_step 节点类型",
    )
    status: Literal["running", "done", "pass", "fail", "skipped", "error"] | None = Field(
        default=None,
        description="workflow_step / verification 状态",
    )
    title: str | None = Field(default=None, description="workflow_step 标题")
    detail: str | None = Field(default=None, description="workflow_step 详情")


# ── 会话管理 ─────────────────────────────────────────────────

class SessionResponse(BaseModel):
    """GET /v1/sessions/{id} 的响应体：返回指定会话的全部历史消息。"""

    session_id: str
    messages: list[ChatMessage]


class SessionSummary(BaseModel):
    """会话列表项：含时间与消息条数。"""

    session_id: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    project_id: str = "default"


class SessionListResponse(BaseModel):
    """GET /v1/sessions 响应。"""

    sessions: list[SessionSummary] = Field(default_factory=list)
    total: int = 0


class AgentInfo(BaseModel):
    """单个 Agent 角色元数据。"""

    name: str
    description: str = ""
    rag_enabled: bool = False
    default_tool_patterns: list[str] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    """GET /v1/agents 响应。"""

    orchestration_backend: str
    agents: list[AgentInfo] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """GET /health 的响应体：确认服务已启动且配置正确加载。"""

    status: str
    model: str
    reasoning_effort: str


# ── MCP 状态 ─────────────────────────────────────────────────

class MCPToolInfo(BaseModel):
    """单个 MCP 工具的描述信息。"""
    qualified_name: str
    tool_name: str
    description: str = ""


class MCPServerInfo(BaseModel):
    """单个 MCP Server 的连接状态与工具列表。"""
    name: str
    enabled: bool = True
    connected: bool = False
    tools: list[MCPToolInfo] = Field(default_factory=list)


class MCPStatusResponse(BaseModel):
    """GET /v1/mcp/status 响应：服务端 MCP 开关与连接状态。"""

    server_enabled: bool = Field(description="服务端 ENABLE_MCP 配置")
    connected: bool = Field(description="MCP Client 是否已连接")
    servers: list[MCPServerInfo] = Field(default_factory=list)


# ── RAG 文档 ─────────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    """POST /v1/documents 请求体：上传文档到课题共享 RAG（会话用于溯源）。"""

    session_id: str = Field(..., min_length=1, description="上传操作所属会话 ID")
    project_id: str | None = Field(default=None, description="课题 ID；缺省由会话反查")
    content: str = Field(..., min_length=1, description="文档正文（markdown 或纯文本）")
    title: str | None = Field(default=None, description="文档标题")
    source: str = Field(default="", description="来源路径或 URL")
    doc_id: str | None = Field(default=None, description="可选：指定文档 ID（覆盖更新）")


class DocumentInfo(BaseModel):
    """已索引文档的元数据。"""
    doc_id: str
    session_id: str
    project_id: str = "default"
    title: str
    source: str = ""
    chunk_count: int = 0
    created_at: str


class DocumentListResponse(BaseModel):
    """GET /v1/documents 响应。"""
    documents: list[DocumentInfo] = Field(default_factory=list)
    total: int = 0


class DocumentUploadResponse(BaseModel):
    """POST /v1/documents 响应。"""
    document: DocumentInfo
    status: str = "indexed"


class SessionRagRef(BaseModel):
    """单条会话 RAG 引用：doc_id + 内容片段预览。"""
    doc_id: str
    snippet: str = ""
    created_at: str | None = None


class SessionRagRefsResponse(BaseModel):
    """GET /v1/sessions/{id}/rag-refs 响应。"""
    session_id: str
    refs: list[SessionRagRef] = Field(default_factory=list)


# ── Token 用量统计 ───────────────────────────────────────────

class TokenUsageAgentBreakdown(BaseModel):
    """按 Agent 分组的 token 用量。"""
    agent_name: str
    event_count: int = 0
    total_tokens: int = 0


class TokenUsageTotals(BaseModel):
    """汇总 token 用量。"""
    event_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenUsageStatsResponse(BaseModel):
    """GET /v1/stats/tokens 响应。"""
    filters: dict[str, str | None] = Field(default_factory=dict)
    totals: TokenUsageTotals
    by_agent: list[TokenUsageAgentBreakdown] = Field(default_factory=list)


# ── L4 结构化科研记忆 ─────────────────────────────────────────

class StructuredMemoryEntry(BaseModel):
    """单条结构化记忆（定理、假设、实验结论、引用等）。"""

    id: int | None = None
    session_id: str | None = None
    kind: Literal["theorem", "hypothesis", "conclusion", "citation", "note"] = "note"
    title: str = ""
    body: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class StructuredMemoryCreateRequest(BaseModel):
    """POST /v1/memory/structured 请求体。"""

    session_id: str | None = None
    kind: Literal["theorem", "hypothesis", "conclusion", "citation", "note"] = "note"
    title: str = ""
    body: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredMemoryListResponse(BaseModel):
    """GET /v1/memory/structured 响应。"""

    entries: list[StructuredMemoryEntry] = Field(default_factory=list)
    total: int = 0


class MemoryEdge(BaseModel):
    """知识图谱边。"""

    id: int | None = None
    from_id: int
    to_id: int
    relation: Literal["depends_on", "contradicts", "supports", "cites"] = "depends_on"
    created_at: str | None = None


class MemoryGraphResponse(BaseModel):
    """GET /v1/memory/structured/graph 响应。"""

    nodes: list[StructuredMemoryEntry] = Field(default_factory=list)
    edges: list[MemoryEdge] = Field(default_factory=list)


class MemoryEdgeCreateRequest(BaseModel):
    """POST /v1/memory/structured/{id}/edges 请求体。"""

    to_id: int
    relation: Literal["depends_on", "contradicts", "supports", "cites"] = "depends_on"


class WorkspaceFileInfo(BaseModel):
    """理论工作区文件条目。"""

    path: str
    kind: str = "file"


class WorkspaceListResponse(BaseModel):
    """GET /v1/theory/workspace 响应。"""

    files: list[WorkspaceFileInfo] = Field(default_factory=list)


class ExperimentRunInfo(BaseModel):
    """实验运行记录。"""

    run_id: str
    name: str = ""
    config_path: str = ""
    status: str = "completed"
    log_path: str = ""
    created_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ExperimentRunsResponse(BaseModel):
    """GET /v1/experiments/runs 响应。"""

    runs: list[ExperimentRunInfo] = Field(default_factory=list)
    total: int = 0


class LatexExportRequest(BaseModel):
    """POST /v1/export/* 请求体。"""

    session_id: str | None = None
    title: str = "Theory Export"
    include_global: bool = True
    include_chat: bool = True
    project_id: str = "default"
    use_ai: bool = False
    ai_instructions: str | None = None


class ExportPolishResponse(BaseModel):
    """POST /v1/export/polish 响应。"""

    markdown: str
    ai_applied: bool = False
    message: str = ""


class ExportPreviewResponse(BaseModel):
    """GET /v1/export/preview 响应。"""

    entry_count: int = 0
    session_structured_count: int = 0
    global_structured_count: int = 0
    chat_message_count: int = 0
    source: str = "empty"
    hint: str = ""


class LatexExportResponse(BaseModel):
    """POST /v1/export/latex 响应。"""

    latex: str
    path: str | None = None
    bib_path: str | None = None


# ── 课题（Project）─────────────────────────────────────────────

class ProjectInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    created_by: str = ""
    default_assumptions: list[str] = Field(default_factory=list)
    workspace_path: str = ""
    rag_namespace: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class ProjectListResponse(BaseModel):
    projects: list[ProjectInfo] = Field(default_factory=list)
    total: int = 0


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    created_by: str = ""


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class ProjectMemberInfo(BaseModel):
    id: int
    project_id: str
    user_id: str
    role: Literal["pi", "theorist", "experimenter", "reviewer", "literature"]
    created_at: str | None = None


class ProjectTaskInfo(BaseModel):
    id: int
    project_id: str
    title: str
    description: str = ""
    assignee_role: str = "theorist"
    status: Literal["todo", "in_progress", "blocked", "done"] = "todo"
    related_entry_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProjectTasksResponse(BaseModel):
    tasks: list[ProjectTaskInfo] = Field(default_factory=list)
    total: int = 0


class ProjectTaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    assignee_role: str = "theorist"
    related_entry_id: int | None = None


class ProjectSessionInfo(BaseModel):
    session_id: str
    project_id: str


class ProjectSessionsResponse(BaseModel):
    sessions: list[ProjectSessionInfo] = Field(default_factory=list)
    total: int = 0


# ── 验证账本 ──────────────────────────────────────────────────

class VerificationRecordInfo(BaseModel):
    id: int
    project_id: str = "default"
    session_id: str | None = None
    entry_id: int | None = None
    claim_id: str = ""
    tier: Literal["symbolic", "numerical", "experiment"] = "numerical"
    executor: str = ""
    agent_name: str = ""
    passed: bool = False
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    created_at: str | None = None


class VerificationRecordsResponse(BaseModel):
    records: list[VerificationRecordInfo] = Field(default_factory=list)
    total: int = 0


class VerificationDashboardResponse(BaseModel):
    project_id: str = "default"
    total_records: int = 0
    passed: int = 0
    failed: int = 0
    by_tier: dict[str, int] = Field(default_factory=dict)
    recent: list[VerificationRecordInfo] = Field(default_factory=list)


class VerificationClaimRequest(BaseModel):
    claim: dict[str, Any]
    session_id: str | None = None
    project_id: str = "default"
    entry_id: int | None = None
    persist: bool = True


class ExperimentRunRequest(BaseModel):
    config_path: str = Field(..., min_length=1)
    session_id: str | None = None


# ── 同步 / 可观测性 ───────────────────────────────────────────

class SyncMetadataRequest(BaseModel):
    project_id: str = "default"
    session_id: str | None = None
    actor: str = ""


class SyncMetadataResponse(BaseModel):
    project_id: str
    synced_entries: int = 0
    metadata: list[dict[str, Any]] = Field(default_factory=list)


class ObservabilitySummary(BaseModel):
    project_id: str = "default"
    verification_total: int = 0
    verification_passed: int = 0
    verification_pass_rate: float = 0.0
    by_agent: dict[str, dict[str, int]] = Field(default_factory=dict)


class AgentQualityResponse(BaseModel):
    agents: list[dict[str, Any]] = Field(default_factory=list)


# ── Jupyter 桥接 ──────────────────────────────────────────────

class NotebookResultUploadRequest(BaseModel):
    name: str = "notebook_result"
    project_id: str = "default"
    session_id: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class NotebookResultUploadResponse(BaseModel):
    run_id: str
    log_path: str
    status: str = "indexed"


class WorkspaceWriteRequest(BaseModel):
    content: str = Field(..., min_length=0)


class AssumptionDagResponse(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class BibliographyEntryInfo(BaseModel):
    id: int | None = None
    project_id: str = "default"
    bib_key: str
    title: str = ""
    authors: str = ""
    year: str = ""
    arxiv_id: str = ""
    doi: str = ""
    raw_bibtex: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class BibliographyListResponse(BaseModel):
    entries: list[BibliographyEntryInfo] = Field(default_factory=list)
    total: int = 0


# ── 科研 Campaign ──────────────────────────────────────────────

CampaignStageId = Literal[
    "S0_campaign",
    "S1_literature",
    "S2_formalization",
    "S3_theory",
    "S4_counterexample",
    "S5_experiment",
    "S6_synthesis",
    "S7_review",
    "S8_archive",
    "complete",
]

CampaignGateStatus = Literal["pending", "pass", "fail", "skipped"]


class ResearchCampaignInfo(BaseModel):
    id: str
    project_id: str = "default"
    title: str
    task_family: str = "loss_landscape_critical_points"
    dataset: str = ""
    benchmark: str = ""
    sota_reference: list[str] = Field(default_factory=list)
    compute_budget: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    current_stage: CampaignStageId = "S0_campaign"
    status: Literal["active", "blocked", "done", "iterate"] = "active"
    stage_artifacts: dict[str, Any] = Field(default_factory=dict)
    gates: dict[str, CampaignGateStatus] = Field(default_factory=dict)
    session_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ResearchCampaignListResponse(BaseModel):
    campaigns: list[ResearchCampaignInfo] = Field(default_factory=list)
    total: int = 0


class ResearchCampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    task_family: str = "loss_landscape_critical_points"
    dataset: str = ""
    benchmark: str = ""
    sota_reference: list[str] = Field(default_factory=list)
    compute_budget: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    session_id: str | None = None


class ResearchCampaignUpdateRequest(BaseModel):
    current_stage: CampaignStageId | None = None
    status: Literal["active", "blocked", "done", "iterate"] | None = None
    stage_artifacts: dict[str, Any] | None = None
    gates: dict[str, CampaignGateStatus] | None = None


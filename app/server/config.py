# =============================================================================
# 应用配置模块。
#
# 职责：从 conf/.env（或兼容根目录 .env）与环境变量加载运行时配置。
#       通过 get_settings() 提供全局可访问的单例配置对象。
#
# 架构位置（被以下模块引用）：
#     - server/main.py         → setup_logging + 打印配置摘要
#     - server/llm/client.py   → 读取 API 密钥、模型名、max_tokens 等
#     - server/api/chat.py     → 读出日志级别等
#
# 主要依赖：pydantic-settings — 字段名自动匹配 .env 变量名（忽略大小写）并转换类型。
#
# 加载顺序：
#     1. 构造 Settings() 对象
#     2. pydantic-settings 搜索当前目录 .env 文件
#     3. 若找到，注入变量到对应字段；若未找到，使用 Field(default=...) 默认值
#     4. 应用 field_validator 校验（如 API Key 不能是占位符）
#
# Debug：
#     - 启动报 ValidationError: deepseek_api_key Field required → conf/.env 未配置
#     - 启动报 ValueError → .env 中 DEEPSEEK_API_KEY 为空或仍是 sk-your-api-key-here
#     - 模型无 reasoning 输出 → 检查 REASONING_EFFORT 是否为 max
# =============================================================================

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from server.llm.prompts import DEFAULT_SYSTEM_PROMPT
from shared.paths import DATA_ROOT, LOG_ROOT, conf_path, resolve_env_file

_ENV_FILE = resolve_env_file()
_SETTINGS_KW: dict = {
    "env_file_encoding": "utf-8",
    "case_sensitive": False,
    "extra": "ignore",
}
if _ENV_FILE.is_file():
    _SETTINGS_KW["env_file"] = str(_ENV_FILE)


class Settings(BaseSettings):
    # 全局配置类。属性名与 .env 变量名一一对应（不区分大小写）。
    #
    # 使用方式：
    #     cfg = get_settings()
    #     print(cfg.model)      # → deepseek-v4-pro

    # pydantic-settings 配置：从 .env 读取，大小写不敏感，忽略未定义的额外变量
    model_config = SettingsConfigDict(**_SETTINGS_KW)

    # ── DeepSeek LLM ────────────────────────────────────────

    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API 密钥（必填）",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API 根地址，一般无需修改",
    )
    model: str = Field(
        default="deepseek-v4-pro",
        description="模型 ID：deepseek-v4-pro / deepseek-v4-flash 等",
    )
    max_tokens: int = Field(
        default=384_000,
        description="单次请求最大输出 token 数（thinking max 需要较大预算）",
    )
    reasoning_effort: str = Field(
        default="max",
        description="DeepSeek 推理强度：high 或 max",
    )

    # ── 服务监听参数 ─────────────────────────────────────────

    host: str = Field(
        default="0.0.0.0",
        description="uvicorn 监听地址。0.0.0.0 允许外部访问；Nginx 代理时改 127.0.0.1",
    )
    port: int = Field(
        default=8000,
        description="uvicorn 监听端口",
    )
    log_level: str = Field(
        default="INFO",
        description="日志级别：INFO=常规，DEBUG=打印 LLM 请求摘要",
    )
    log_format: str = Field(
        default="text",
        description="日志格式：text=人类可读，json=结构化 JSON（Docker/可观测推荐）",
    )
    enable_token_stats: bool = Field(
        default=True,
        description="是否将 LLM token 用量写入 SQLite 聚合表",
    )

    # ── Agent 参数 ───────────────────────────────────────────

    default_system_prompt: str = Field(
        default=DEFAULT_SYSTEM_PROMPT,
        description="默认 system prompt，可被客户端请求中的 system_prompt 字段覆盖",
    )
    max_history_messages: int = Field(
        default=0,
        description="每轮对话携带的历史消息条数上限。0 表示不限制（全量传入）",
    )

    # ── 会话存储（Phase 2A） ─────────────────────────────────

    session_store_backend: str = Field(
        default="sqlite",
        description="会话存储后端：memory（内存，重启丢失）或 sqlite（持久化）",
    )
    session_db_path: str = Field(
        default=str(DATA_ROOT / "sessions.db"),
        description="SQLite 数据库文件路径（仅 session_store_backend=sqlite 时生效）",
    )
    enable_history_summary: bool = Field(
        default=False,
        description="历史截断时是否对丢弃部分做 LLM 摘要（需额外 API 调用）",
    )
    history_summary_max_tokens: int = Field(
        default=1024,
        description="历史摘要的最大输出 token 数",
    )

    # ── MCP 工具层（Phase 2B） ───────────────────────────────

    enable_mcp: bool = Field(
        default=False,
        description="是否启用 MCP 工具调用",
    )
    mcp_config_path: str = Field(
        default=str(conf_path("mcp_servers.json")),
        description="MCP Server 配置文件路径",
    )
    mcp_allowed_dirs: str = Field(
        default=f"{DATA_ROOT / 'mcp_files'}:{DATA_ROOT / 'projects'}",
        description="filesystem MCP 允许访问的目录（冒号分隔）；不含 data/theory 种子",
    )
    mcp_max_tool_rounds: int = Field(
        default=10,
        description="单轮对话最多工具调用轮次",
    )
    mcp_tool_result_max_chars: int = Field(
        default=8000,
        description="工具结果写入 LLM 上下文前的最大字符数（超出则截断并附摘要提示）",
    )
    mcp_tool_whitelist: str = Field(
        default="",
        description="全局工具白名单：逗号分隔 glob 模式（如 filesystem__*,arxiv__*）；空=全部",
    )
    mcp_tool_whitelist_path: str = Field(
        default=str(conf_path("mcp_tool_whitelist.json")),
        description="可选 JSON 白名单文件路径，支持 global 与 agents 映射",
    )

    # ── 编排后端（Phase 3） ──────────────────────────────────

    orchestration_backend: str = Field(
        default="legacy",
        description="Agent 编排：legacy、langgraph 或 multi（与 langgraph 相同）",
    )
    router_use_llm: bool = Field(
        default=False,
        description="意图路由是否优先使用 LLM（失败回退关键词规则）",
    )
    tavily_api_key: str = Field(
        default="",
        description="Tavily 搜索 API Key；设置后 web_search MCP 优先使用 Tavily",
    )

    # ── L3 向量记忆 / RAG（Phase 5） ─────────────────────────

    enable_rag: bool = Field(
        default=False,
        description="是否启用 L3 向量记忆检索",
    )
    rag_chroma_path: str = Field(
        default=str(DATA_ROOT / "chroma"),
        description="Chroma 向量库持久化目录",
    )
    rag_embedding_provider: str = Field(
        default="chroma_default",
        description="Embedding 提供方：chroma_default、sentence_transformers、openai 或 test（仅测试）",
    )
    rag_embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding 模型名（sentence-transformers 或 OpenAI 兼容 API）；chroma_default 时忽略",
    )
    rag_embedding_base_url: str = Field(
        default="",
        description="OpenAI 兼容 Embedding API 根地址；空则使用 DEEPSEEK_BASE_URL",
    )
    rag_chunk_size: int = Field(
        default=800,
        ge=100,
        description="文档分块字符数",
    )
    rag_chunk_overlap: int = Field(
        default=100,
        ge=0,
        description="分块重叠字符数",
    )
    rag_retrieval_top_k: int = Field(
        default=4,
        ge=1,
        description="每次检索返回的片段数",
    )
    rag_agents: str = Field(
        default="literature,theory,general",
        description="启用 RAG 检索的 Agent 列表（逗号分隔）；含 general 时 legacy 模式也注入",
    )
    rag_index_mcp_files: bool = Field(
        default=False,
        description="启动时是否索引 MCP_ALLOWED_DIRS 下的 markdown/text 文件",
    )

    # ── L4 结构化记忆注入 ─────────────────────────────────────

    structured_memory_agents: str = Field(
        default="theory,experiment,review",
        description="启用 L4 结构化记忆注入的 Agent 列表（逗号分隔）",
    )

    # ── 理论工作区与研究流水线 ─────────────────────────────────

    theory_workspace_path: str = Field(
        default=str(DATA_ROOT / "theory"),
        description="理论工作区根目录（symbols.md、assumptions.md 等）",
    )
    experiments_path: str = Field(
        default=str(DATA_ROOT / "experiments"),
        description="实验工作区根目录",
    )
    research_pipeline_mode: str = Field(
        default="single",
        description=(
            "研究模式：single=单 Agent；auto=场景工作流（2–3 跳）；"
            "auto=场景工作流；single=单 Agent"
        ),
    )
    enable_artifact_store: bool = Field(
        default=True,
        description="是否启用理论侧 Artifact 持久化与解析",
    )
    enable_numerical_mcp: bool = Field(
        default=True,
        description="是否在 MCP 配置中启用 numerical 数值验证服务",
    )
    global_memory_sync: bool = Field(
        default=True,
        description="启动时是否将 data/theory/lemmas/ 同步到 L4 全局记忆",
    )
    pdf_ingest_enabled: bool = Field(
        default=True,
        description="是否启用 PDF 文档解析入库",
    )

    # ── 校验器 ───────────────────────────────────────────────

    @field_validator("deepseek_api_key")
    @classmethod
    def strip_api_key(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort(cls, value: str) -> str:
        # 启动时校验推理强度：仅允许 high 或 max。
        normalized = value.strip().lower()
        if normalized not in ("high", "max"):
            raise ValueError(f"REASONING_EFFORT 必须是 high 或 max，当前为: {value}")
        return normalized

    @model_validator(mode="after")
    def validate_deepseek_api_key(self) -> Settings:
        placeholder = "sk-your-api-key-here"
        key = self.deepseek_api_key
        if not key or key == placeholder:
            raise ValueError(
                "DEEPSEEK_API_KEY 未配置或为占位符。"
                "请复制 conf/.env.example 为 conf/.env 并填入真实密钥。"
            )
        return self

    @field_validator("session_store_backend")
    @classmethod
    def validate_session_store_backend(cls, value: str) -> str:
        # 启动时校验会话存储后端：仅允许 memory 或 sqlite。
        normalized = value.strip().lower()
        if normalized not in ("memory", "sqlite"):
            raise ValueError(
                f"SESSION_STORE_BACKEND 必须是 memory 或 sqlite，当前为: {value}"
            )
        return normalized

    @field_validator("orchestration_backend")
    @classmethod
    def validate_orchestration_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "multi":
            return "langgraph"
        if normalized not in ("legacy", "langgraph"):
            raise ValueError(
                f"ORCHESTRATION_BACKEND 必须是 legacy、langgraph 或 multi，当前为: {value}"
            )
        return normalized

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ("text", "json"):
            raise ValueError(f"LOG_FORMAT 必须是 text 或 json，当前为: {value}")
        return normalized

    @field_validator("rag_embedding_provider")
    @classmethod
    def validate_rag_embedding_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = ("chroma_default", "sentence_transformers", "openai", "test")
        if normalized not in allowed:
            raise ValueError(
                f"RAG_EMBEDDING_PROVIDER 必须是 {', '.join(allowed)}，当前为: {value}"
            )
        return normalized

    def rag_agent_names(self) -> list[str]:
        """解析 RAG_AGENTS 配置为 Agent 名称列表。"""
        return [
            part.strip().lower()
            for part in self.rag_agents.split(",")
            if part.strip()
        ]

    def structured_memory_agent_names(self) -> list[str]:
        """解析 STRUCTURED_MEMORY_AGENTS 为 Agent 名称列表。"""
        return [
            part.strip().lower()
            for part in self.structured_memory_agents.split(",")
            if part.strip()
        ]

    # ── 工具方法 ─────────────────────────────────────────────

    def masked_api_key(self) -> str:
        # 返回脱敏后的 API Key（只保留后 4 位），用于启动日志打印。
        key = self.deepseek_api_key
        if len(key) <= 8:
            return "sk-***"
        return f"sk-***{key[-4:]}"


@lru_cache
def get_settings() -> Settings:
    # 获取全局配置单例（带缓存）。
    # 首次调用时读取 .env 构建实例；后续返回缓存中的同一对象。
    return Settings()


def setup_logging(settings: Settings | None = None) -> None:
    """
    初始化根 logger：控制台输出 + 写入 log/app.log。

    参数:
        settings: 可选 Settings；省略时调用 get_settings()
    """
    cfg = settings or get_settings()
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    log_file = LOG_ROOT / "app.log"

    handlers: list[logging.Handler] = []
    if cfg.log_format == "json":
        from server.observability.structured import StructuredLogFormatter

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(StructuredLogFormatter())
        handlers.append(stream_handler)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StructuredLogFormatter())
        handlers.append(file_handler)
    else:
        text_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        formatter = logging.Formatter(text_fmt)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers, force=True)

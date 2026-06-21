# =============================================================================
# 应用配置模块。
#
# 职责：从项目根目录 .env 文件与环境变量加载所有运行时配置。
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
#     - 启动报 ValidationError: deepseek_api_key Field required → 根目录没有 .env
#     - 启动报 ValueError → .env 中 DEEPSEEK_API_KEY 为空或仍是 sk-your-api-key-here
#     - 模型无 reasoning 输出 → 检查 REASONING_EFFORT 是否为 max
# =============================================================================

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from server.llm.prompts import DEFAULT_SYSTEM_PROMPT


class Settings(BaseSettings):
    # 全局配置类。属性名与 .env 变量名一一对应（不区分大小写）。
    #
    # 使用方式：
    #     cfg = get_settings()
    #     print(cfg.model)      # → deepseek-v4-pro

    # pydantic-settings 配置：从 .env 读取，大小写不敏感，忽略未定义的额外变量
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # .env 中的 DEEPSEEK_API_KEY 匹配字段 deepseek_api_key
        extra="ignore",         # .env 中有未定义变量不会导致启动失败
    )

    # ── DeepSeek API 参数 ────────────────────────────────────

    deepseek_api_key: str = Field(
        ...,
        description="DeepSeek API 密钥，从 platform.deepseek.com 获取",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API 根地址，一般无需修改",
    )
    model: str = Field(
        default="deepseek-v4-pro",
        description="模型 ID。可选 deepseek-v4-flash（更快/更便宜）",
    )
    max_tokens: int = Field(
        default=384_000,
        description="单次请求最大输出 token 数。384000 为 V4 天花板，为 thinking max 留出预算",
    )
    reasoning_effort: str = Field(
        default="max",
        description="推理强度：high=一般推理，max=最强推理（消耗更多 token，响应更慢）",
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
        default="./data/sessions.db",
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
        default="./mcp_servers.json",
        description="MCP Server 配置文件路径",
    )
    mcp_allowed_dirs: str = Field(
        default="./data/mcp_files",
        description="filesystem MCP 允许访问的目录（冒号分隔多个路径）",
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
        default="",
        description="可选 JSON 白名单文件路径，支持 global 与 agents 映射",
    )

    # ── 编排后端（Phase 3） ──────────────────────────────────

    orchestration_backend: str = Field(
        default="legacy",
        description="Agent 编排后端：legacy（自研 tool loop）或 langgraph",
    )

    # ── 校验器 ───────────────────────────────────────────────

    @field_validator("deepseek_api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        # 启动时校验 API Key：不能是空字符串，不能是占位符。
        stripped = value.strip()
        if not stripped or stripped == "sk-your-api-key-here":
            raise ValueError(
                "DEEPSEEK_API_KEY 未配置或为占位符。"
                "请复制 .env.example 为 .env 并填入真实密钥。"
            )
        return stripped

    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort(cls, value: str) -> str:
        # 启动时校验推理强度：仅允许 high 或 max。
        normalized = value.strip().lower()
        if normalized not in ("high", "max"):
            raise ValueError(f"REASONING_EFFORT 必须是 high 或 max，当前为: {value}")
        return normalized

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
        if normalized not in ("legacy", "langgraph"):
            raise ValueError(
                f"ORCHESTRATION_BACKEND 必须是 legacy 或 langgraph，当前为: {value}"
            )
        return normalized

    # ── 工具方法 ─────────────────────────────────────────────

    def masked_api_key(self) -> str:
        # 返回脱敏后的 API Key（只保留后 4 位），用于启动日志打印。
        # 示例：sk-abc...xyz9 → sk-***xyz9
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
    # 按配置指定的日志级别初始化 Python 根 logger。
    # 参数 settings 为 None 时自动调用 get_settings()。
    #
    # 调用方：server/main.py 在应用启动阶段调用。
    cfg = settings or get_settings()
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

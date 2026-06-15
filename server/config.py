"""
应用配置模块。

职责：
    从 .env 文件与环境变量加载所有运行时配置，并提供全局单例 settings。

架构位置：
    server/main.py 启动时加载
    server/llm/client.py 读取 API 密钥与模型参数
    server/api/chat.py 读取日志级别等

主要依赖：
    pydantic-settings — 类似 C++ 中从配置文件 + 环境变量构建 Config 单例

Debug：
    - 启动报 ValidationError：检查 .env 是否存在且 DEEPSEEK_API_KEY 已填写
    - 模型无 reasoning 输出：确认 REASONING_EFFORT=max
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from server.llm.prompts import DEFAULT_SYSTEM_PROMPT


class Settings(BaseSettings):
    """
    全局配置类。字段名与环境变量一一对应（不区分大小写）。

    类比 C++：类似 struct AppConfig，在 main() 启动时 load 一次，全局只读访问。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # 允许 .env 中的变量名与字段名大小写不敏感匹配
        case_sensitive=False,
        extra="ignore",
    )

    # --- DeepSeek API ---
    deepseek_api_key: str = Field(..., description="DeepSeek API 密钥")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API 基础 URL（OpenAI 兼容端点）",
    )
    model: str = Field(default="deepseek-v4-pro", description="模型 ID")
    max_tokens: int = Field(default=384_000, description="最大输出 token 数")
    reasoning_effort: str = Field(default="max", description="推理强度：high 或 max")

    # --- 服务 ---
    host: str = Field(default="0.0.0.0", description="uvicorn 监听地址")
    port: int = Field(default=8000, description="uvicorn 监听端口")
    log_level: str = Field(default="INFO", description="日志级别：INFO 或 DEBUG")

    # --- Agent ---
    default_system_prompt: str = Field(
        default=DEFAULT_SYSTEM_PROMPT,
        description="默认 system prompt，可被请求体 system_prompt 覆盖",
    )
    # Phase 2 预留：历史消息条数上限，0 表示不限制
    max_history_messages: int = Field(default=0, description="会话历史条数上限，0=不限制")

    @field_validator("deepseek_api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        """启动时校验 API Key 非空且不是占位符。"""
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
        """只允许 high 或 max。"""
        normalized = value.strip().lower()
        if normalized not in ("high", "max"):
            raise ValueError(f"REASONING_EFFORT 必须是 'high' 或 'max'，当前为: {value}")
        return normalized

    def masked_api_key(self) -> str:
        """
        返回脱敏后的 API Key，用于启动日志打印。

        示例：sk-abc...xyz9 → sk-***xyz9
        """
        key = self.deepseek_api_key
        if len(key) <= 8:
            return "sk-***"
        return f"sk-***{key[-4:]}"


@lru_cache
def get_settings() -> Settings:
    """
    获取配置单例（带缓存）。

    类比 C++：类似 Meyers Singleton，首次调用时构造，之后返回同一实例。
    lru_cache 确保整个进程生命周期内只加载一次 .env。
    """
    return Settings()


def setup_logging(settings: Settings | None = None) -> None:
    """
    根据 settings.log_level 配置根 logger。

    设置 LOG_LEVEL=DEBUG 时，会打印 LLM 请求摘要，便于排查 API 问题。
    """
    cfg = settings or get_settings()
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

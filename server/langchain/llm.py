# =============================================================================
# LangChain LLM 工厂 — DeepSeek via ChatOpenAI。
#
# 职责：为 LangGraph / LangChain 路径提供与 DeepSeekClient 对齐的模型配置。
# 生产路径仍默认 legacy（server/llm/client.py）；本模块供 Phase 3+ 渐进迁移。
# =============================================================================

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from server.config import Settings, get_settings


def build_chat_model_kwargs(
    settings: Settings,
    *,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    enable_thinking: bool = True,
) -> dict[str, Any]:
    """构造 ChatOpenAI 参数，与 DeepSeekClient._build_create_kwargs 对齐。"""
    effort = reasoning_effort or settings.reasoning_effort
    return {
        "model": settings.model,
        "api_key": settings.deepseek_api_key,
        "base_url": settings.deepseek_base_url,
        "max_tokens": max_tokens if max_tokens is not None else settings.max_tokens,
        "reasoning_effort": effort,
        "extra_body": {
            "thinking": {"type": "enabled" if enable_thinking else "disabled"},
        },
    }


def get_chat_model(
    settings: Settings | None = None,
    *,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    enable_thinking: bool = True,
) -> ChatOpenAI:
    """创建 DeepSeek 兼容的 ChatOpenAI 实例。"""
    cfg = settings or get_settings()
    kwargs = build_chat_model_kwargs(
        cfg,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )
    return ChatOpenAI(**kwargs)

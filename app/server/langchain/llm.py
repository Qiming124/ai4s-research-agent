"""
LangChain LLM 工厂 — DeepSeek via ChatOpenAI。

职责：为 LangGraph / LangChain 路径提供与 DeepSeekClient 对齐的模型配置。

关键区别：
    - LangChain ChatOpenAI 自动处理 reasoning_content → additional_kwargs
    - build_chat_model_kwargs 对齐 DeepSeekClient._build_create_kwargs 参数
    - thinking 通过 extra_body 注入 {"thinking": {"type": "enabled"}}
"""

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
    """
    构造 ChatOpenAI 初始化参数，与 DeepSeekClient._build_create_kwargs 对齐。

    参数:
        settings: 运行时配置
        reasoning_effort: 推理强度（None=使用 .env 默认值）
        max_tokens: 最大输出 token（None=使用 .env 默认值）
        enable_thinking: 是否启用 DeepSeek thinking 模式

    返回:
        ChatOpenAI 构造参数字典
    """
    effort = reasoning_effort or settings.reasoning_effort
    return {
        "model": settings.model,
        "api_key": settings.deepseek_api_key,
        "base_url": settings.deepseek_base_url,
        "max_tokens": max_tokens if max_tokens is not None else settings.max_tokens,
        "reasoning_effort": effort,
        # extra_body 传给 OpenAI SDK → DeepSeek API
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
    """
    创建 DeepSeek 兼容的 LangChain ChatOpenAI 实例。

    使用场景：
        - LangGraph ReAct 子图的 tool_model（thinking=off，加速工具调用）
        - LangGraph 子图的 final_model（thinking=enabled，含 reasoning 输出）

    参数:
        settings: 运行时配置（None=全局 get_settings）
        reasoning_effort: 推理强度
        max_tokens: 最大输出 token
        enable_thinking: 是否启用 thinking 模式
    """
    cfg = settings or get_settings()
    kwargs = build_chat_model_kwargs(
        cfg,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )
    return ChatOpenAI(**kwargs)

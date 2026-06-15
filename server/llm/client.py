"""
DeepSeek LLM 客户端封装。

职责：
    封装 OpenAI SDK 对 DeepSeek API 的调用，支持流式与非流式对话，
    并解析 reasoning（thinking）与 content 两种输出流。

架构位置：
    server/agents/general.py 调用本模块
    server/llm/client.py 是唯一直接访问 DeepSeek HTTP API 的模块

主要依赖：
    openai.AsyncOpenAI — OpenAI 官方异步 SDK，DeepSeek 完全兼容其 Chat Completions 接口

关键概念（C++ 对照）：
    - AsyncOpenAI：带连接池的 HTTP Client 单例
    - async for chunk in response：类似 co_await 消费异步迭代器 / generator

Debug：
    - 401 Unauthorized：DEEPSEEK_API_KEY 无效或过期
    - 空 reasoning：确认 reasoning_effort="max" 且 extra_body thinking enabled
    - 连接超时：检查网络与 DEEPSEEK_BASE_URL
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, AuthenticationError, APIConnectionError, APIStatusError

from server.config import Settings, get_settings
from shared.schemas import StreamChunk

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    DeepSeek V4 API 客户端。

    使用 OpenAI SDK 的兼容模式：只需修改 base_url 即可调用 DeepSeek，
    无需更换 SDK 或重写 HTTP 逻辑。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        初始化客户端。

        Args:
            settings: 配置对象；为 None 时使用全局 get_settings()

        Debug:
            若此处未报错但后续 401，说明 key 格式正确但权限/余额有问题。
        """
        self._settings = settings or get_settings()
        # AsyncOpenAI 内部维护 httpx 连接池，类似 C++ 中复用的 HTTP client
        self._client = AsyncOpenAI(
            api_key=self._settings.deepseek_api_key,
            base_url=self._settings.deepseek_base_url,
        )

    def _build_create_kwargs(self, messages: list[dict[str, str]], *, stream: bool) -> dict[str, Any]:
        """
        构造 chat.completions.create 的参数字典。

        DeepSeek V4 特有参数：
            reasoning_effort: "high" | "max" — 控制 thinking 深度
            extra_body.thinking.type: "enabled" — 显式开启 thinking 模式

        max_tokens 设为 384000 是为 thinking max 预留足够输出预算。
        """
        return {
            "model": self._settings.model,
            "messages": messages,
            "max_tokens": self._settings.max_tokens,
            "stream": stream,
            # V4 推理强度（非 OpenAI 标准字段，DeepSeek 扩展）
            "reasoning_effort": self._settings.reasoning_effort,
            # thinking 模式通过 extra_body 传递（OpenAI SDK 的扩展参数机制）
            "extra_body": {"thinking": {"type": "enabled"}},
        }

    async def chat(self, messages: list[dict[str, str]]) -> tuple[str, str | None, dict[str, Any] | None]:
        """
        非流式对话：等待完整响应后一次性返回。

        Args:
            messages: OpenAI 格式消息列表

        Returns:
            (content, reasoning, usage) 三元组

        Raises:
            AuthenticationError: API Key 无效
            APIConnectionError: 网络连接失败
            APIStatusError: API 返回 4xx/5xx

        类比 C++：类似同步 HTTP POST，阻塞直到 body 完整返回。
        """
        kwargs = self._build_create_kwargs(messages, stream=False)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "DeepSeek 非流式请求: model=%s, messages=%d 条, max_tokens=%d",
                kwargs["model"],
                len(messages),
                kwargs["max_tokens"],
            )

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except AuthenticationError as exc:
            logger.error("DeepSeek 认证失败，请检查 DEEPSEEK_API_KEY")
            raise exc
        except APIConnectionError as exc:
            logger.error("无法连接 DeepSeek API: %s", self._settings.deepseek_base_url)
            raise exc

        choice = response.choices[0]
        message = choice.message

        # DeepSeek thinking 模式下，reasoning 可能在 message 的扩展字段中
        reasoning: str | None = getattr(message, "reasoning_content", None)
        content: str = message.content or ""

        usage: dict[str, Any] | None = None
        if response.usage:
            usage = response.usage.model_dump()

        return content, reasoning, usage

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[StreamChunk]:
        """
        流式对话：逐 chunk yield 推理过程与最终回答。

        类比 C++：类似返回 std::generator<StreamChunk> 的协程，调用方用 async for 消费。

        Args:
            messages: OpenAI 格式消息列表

        Yields:
            StreamChunk: type 为 "reasoning" | "content" | "done" | "error"

        Debug:
            - 401: 检查 .env 中 DEEPSEEK_API_KEY
            - 只有 content 无 reasoning: 确认 reasoning_effort 与 thinking.enabled
            - 流中断: 检查网络稳定性或 API 限流
        """
        kwargs = self._build_create_kwargs(messages, stream=True)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "DeepSeek 流式请求: model=%s, messages=%d 条",
                kwargs["model"],
                len(messages),
            )

        try:
            # stream=True 时返回 AsyncStream，可用 async for 迭代
            stream = await self._client.chat.completions.create(**kwargs)
        except AuthenticationError:
            yield StreamChunk(type="error", content="API 认证失败，请检查 DEEPSEEK_API_KEY")
            return
        except APIConnectionError as exc:
            yield StreamChunk(type="error", content=f"无法连接 DeepSeek API: {exc}")
            return
        except APIStatusError as exc:
            yield StreamChunk(type="error", content=f"DeepSeek API 错误 ({exc.status_code}): {exc.message}")
            return

        usage: dict[str, Any] | None = None

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # chunk.choices[0].delta 可能同时含 reasoning_content 与 content
            # 必须先处理 reasoning，再处理 content（两者可能在同一 chunk 出现）
            reasoning_piece = getattr(delta, "reasoning_content", None)
            if reasoning_piece:
                yield StreamChunk(type="reasoning", content=reasoning_piece)

            if delta.content:
                yield StreamChunk(type="content", content=delta.content)

            # 最后一个 chunk 可能携带 usage 统计
            if chunk.usage:
                usage = chunk.usage.model_dump()

        yield StreamChunk(type="done", content="", usage=usage)


# 模块级单例，避免重复创建 HTTP 连接池
_client_instance: DeepSeekClient | None = None


def get_deepseek_client() -> DeepSeekClient:
    """获取 DeepSeekClient 单例。"""
    global _client_instance
    if _client_instance is None:
        _client_instance = DeepSeekClient()
    return _client_instance

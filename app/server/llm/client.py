# =============================================================================
# DeepSeek LLM 客户端封装。
#
# 职责：封装对 DeepSeek API 的 HTTP 调用，是项目中唯一直接访问 DeepSeek 的模块。
#
# 支持两种调用模式：
#     - 流式（stream_chat） → 逐 chunk 返回 StreamChunk，供 SSE 端点使用
#     - 非流式（chat）      → 等待完整响应后一次性返回三部组
#
# 架构位置：server/agents/base.py → GeneralAgent 调用本模块的 stream_chat / chat。
#
# 技术细节：使用 openai.AsyncOpenAI SDK 而非自己写 HTTP 请求。
#           DeepSeek Chat Completions API 与 OpenAI 格式兼容，
#           只需改 base_url 即可复用 SDK 的连接池、重试、流式解析。
#
# Debug：
#     - 401 → .env 中 DEEPSEEK_API_KEY 无效
#     - 有 content 无 reasoning → reasoning_effort 未设 "max" 或 extra_body 未启用 thinking
#     - 连接超时 → 检查网络或 DEEPSEEK_BASE_URL
# =============================================================================

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI, AuthenticationError, APIConnectionError, APIStatusError

from server.config import Settings, get_settings
from server.llm.thinking_messages import prepare_messages_for_deepseek
from shared.schemas import StreamChunk

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatWithToolsResult:
    content: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    usage: dict[str, Any] | None = None


class DeepSeekClient:
    # DeepSeek V4 API 客户端。
    #
    # 封装了 reasoning_effort 推理强度控制、thinking 模式启用、
    # 流式 chunk 解析（reasoning_content 与 content 分离）、异常分类捕获。
    #
    # 典型用法：
    #     client = DeepSeekClient()
    #     async for chunk in client.stream_chat(messages):
    #         print(chunk.type, chunk.content)

    def __init__(self, settings: Settings | None = None) -> None:
        # 初始化 DeepSeek 客户端。
        #
        # 参数 settings 为 None 时自动从全局 get_settings() 读取。
        # 传入自定义 Settings 主要用于单元测试。
        #
        # 内部创建 AsyncOpenAI 实例（通过 httpx 维护 HTTP 连接池）。
        self._settings = settings or get_settings()
        self._client = AsyncOpenAI(
            api_key=self._settings.deepseek_api_key,
            base_url=self._settings.deepseek_base_url,
        )

    def _build_create_kwargs(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool = True,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        # 构造 chat.completions.create() 的参数字典。
        #
        # 参数：
        #     messages — OpenAI 格式消息列表 [{"role":...,"content":...}]
        #     stream   — True=流式，False=一次性返回
        #
        # 返回包含 model、messages、max_tokens、reasoning_effort 等全部必要参数的字典。
        #
        # DeepSeek V4 特有参数：
        #     reasoning_effort        — 控制 thinking 深度，取值 high 或 max
        #     extra_body.thinking     — {"thinking": {"type": "enabled"}} 显式启用 thinking
        #     max_tokens=384000       — 为 thinking max 留够输出预算
        kwargs: dict[str, Any] = {
            "model": self._settings.model,
            "messages": prepare_messages_for_deepseek(messages),
            "max_tokens": max_tokens if max_tokens is not None else self._settings.max_tokens,
            "stream": stream,
            "reasoning_effort": reasoning_effort or self._settings.reasoning_effort,
            "extra_body": {"thinking": {"type": "enabled" if enable_thinking else "disabled"}},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool = True,
    ) -> tuple[str, str | None, dict[str, Any] | None]:
        # 非流式对话：发送消息列表，阻塞等待完整响应后一次性返回。
        #
        # 参数：
        #     messages — OpenAI 格式消息列表
        #
        # 返回 (content, reasoning, usage) 三部组：
        #     content   — 模型最终回答文本（可能为空）
        #     reasoning — 思考过程文本（API 未返回时为 None）
        #     usage     — token 用量字典（API 未返回时为 None）
        #
        # 异常：
        #     AuthenticationError — API Key 无效（401）
        #     APIConnectionError  — 网络不通
        #     APIStatusError      — DeepSeek 返回 4xx/5xx
        #
        # 使用场景：POST /v1/chat、curl 测试、脚本调用。
        kwargs = self._build_create_kwargs(
            messages,
            stream=False,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
        )
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

        # DeepSeek thinking 模式下推理内容在 message.reasoning_content 扩展字段。
        # getattr 安全获取（字段不存在则返回 None）。
        reasoning: str | None = getattr(message, "reasoning_content", None)
        content: str = message.content or ""

        usage: dict[str, Any] | None = None
        if response.usage:
            usage = response.usage.model_dump()

        return content, reasoning, usage

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool = True,
    ) -> ChatWithToolsResult:
        """非流式对话，支持 function calling；返回文本或 tool_calls。"""
        kwargs = self._build_create_kwargs(
            messages,
            stream=False,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            tools=tools,
        )

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except AuthenticationError as exc:
            raise exc
        except APIConnectionError as exc:
            raise exc
        except APIStatusError as exc:
            raise exc

        choice = response.choices[0]
        message = choice.message
        reasoning: str | None = getattr(message, "reasoning_content", None)
        content: str = message.content or ""

        tool_calls: list[ToolCallRequest] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                raw_args = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {"raw": raw_args}
                tool_calls.append(
                    ToolCallRequest(id=tc.id, name=tc.function.name, arguments=args)
                )

        usage: dict[str, Any] | None = None
        if response.usage:
            usage = response.usage.model_dump()

        return ChatWithToolsResult(
            content=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            usage=usage,
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool = True,
    ) -> AsyncIterator[StreamChunk]:
        # 流式对话：发起流式请求，逐 chunk 产出推理过程与最终回答。
        #
        # 参数：
        #     messages — OpenAI 格式消息列表
        #
        # 产出（AsyncIterator[StreamChunk]），每个 chunk 的 type 字段：
        #     "reasoning" — DeepSeek 思考/推理片段
        #     "content"   — 最终回答文本片段
        #     "done"      — 流结束，usage 可能包含 token 统计
        #     "error"     — 发生异常，content 为错误描述
        #
        # 调用方示例：
        #     async for chunk in client.stream_chat(messages):
        #         if chunk.type == "reasoning": ...
        #         elif chunk.type == "content": ...
        #
        # Debug：
        #     - 只有 content 无 reasoning → 确认 reasoning_effort="max" + thinking.enabled
        #     - 流中断 → 网络或 API 限流，查看服务端日志
        kwargs = self._build_create_kwargs(
            messages,
            stream=True,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "DeepSeek 流式请求: model=%s, messages=%d 条",
                kwargs["model"],
                len(messages),
            )

        # 发起流式请求；连接阶段失败则直接 yield error chunk 退出
        try:
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

            # delta 可能同时含 reasoning_content 与 content。
            # 必须先处理 reasoning，再处理 content（顺序不能颠倒）。
            reasoning_piece = getattr(delta, "reasoning_content", None)
            if reasoning_piece:
                yield StreamChunk(type="reasoning", content=reasoning_piece)

            if delta.content:
                yield StreamChunk(type="content", content=delta.content)

            # 最后一个 chunk 可能携带 usage（token 统计）
            if chunk.usage:
                usage = chunk.usage.model_dump()

        # 流结束后发送 done 信号（携带累积的 usage）
        yield StreamChunk(type="done", content="", usage=usage)


# ── 模块级单例 ──────────────────────────────────────────────

_client_instance: DeepSeekClient | None = None


def get_deepseek_client() -> DeepSeekClient:
    # 获取 DeepSeekClient 单例。
    # 首次调用时创建，后续返回同一对象（复用 HTTP 连接池）。
    global _client_instance
    if _client_instance is None:
        _client_instance = DeepSeekClient()
    return _client_instance

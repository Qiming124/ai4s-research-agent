# =============================================================================
# Agent 抽象基类与 GeneralAgent 实现。
#
# Phase 2B：GeneralAgent 支持 MCP 工具调用循环。
# =============================================================================

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from server.config import Settings, get_settings
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.llm.prompts import DEFAULT_SYSTEM_PROMPT, MATH_MODE_SYSTEM_PROMPT
from server.memory.base import BaseSessionStore
from server.memory.manager import MemoryManager, get_memory_manager
from server.memory.session import SessionStore, get_session_store
from server.mcp.client import MCPClient, get_mcp_client
from shared.schemas import ChatMessage, StreamChunk

logger = logging.getLogger(__name__)

_TOOLS_SYSTEM_HINT = (
    "你可以使用提供的工具搜索网络、检索 arXiv 论文或读写实验日志文件。"
    "在需要外部信息时主动调用工具，并在回答中引用工具返回的内容。"
)


class BaseAgent(ABC):
    name: str = "base"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    @abstractmethod
    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        ...


class GeneralAgent(BaseAgent):
    name = "general"

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: DeepSeekClient | None = None,
        session_store: SessionStore | None = None,
        memory_manager: MemoryManager | None = None,
        mcp_client: MCPClient | None = None,
        *,
        math_mode: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm_client or get_deepseek_client()
        self._sessions: BaseSessionStore = session_store or get_session_store()
        self._memory = memory_manager or get_memory_manager()
        self._mcp = mcp_client
        self.system_prompt = MATH_MODE_SYSTEM_PROMPT if math_mode else self._settings.default_system_prompt

    def _with_agent(self, chunk: StreamChunk) -> StreamChunk:
        return chunk.model_copy(update={"agent_name": self.name})

    def _build_messages(
        self,
        history: list[ChatMessage],
        user_message: str,
        system_prompt: str,
        *,
        enable_tools: bool = False,
    ) -> list[dict[str, Any]]:
        prompt = system_prompt
        if enable_tools:
            prompt = f"{prompt}\n\n{_TOOLS_SYSTEM_HINT}"
        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    async def _resolve_mcp(self) -> MCPClient | None:
        if not self._settings.enable_mcp:
            return None
        if self._mcp is not None:
            return self._mcp
        return await get_mcp_client()

    async def _run_tool_loop(
        self,
        api_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        mcp: MCPClient,
    ) -> AsyncIterator[StreamChunk]:
        usage: dict[str, Any] | None = None

        for _round in range(self._settings.mcp_max_tool_rounds):
            result = await self._llm.chat_with_tools(
                api_messages,
                tools,
                enable_thinking=False,
            )
            if result.usage:
                usage = result.usage

            if not result.tool_calls:
                if result.content:
                    yield self._with_agent(StreamChunk(type="content", content=result.content))
                    usage = result.usage or usage
                    yield self._with_agent(StreamChunk(type="done", content="", usage=usage))
                    return
                break

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in result.tool_calls
                ],
            }
            api_messages.append(assistant_msg)

            for tc in result.tool_calls:
                args_json = json.dumps(tc.arguments, ensure_ascii=False)
                yield self._with_agent(
                    StreamChunk(
                        type="tool_call_start",
                        content=args_json,
                        tool_name=tc.name,
                        tool_call_id=tc.id,
                    )
                )
                try:
                    tool_result = await mcp.call_tool(tc.name, tc.arguments)
                    yield self._with_agent(
                        StreamChunk(
                            type="tool_call_result",
                            content=tool_result,
                            tool_name=tc.name,
                            tool_call_id=tc.id,
                        )
                    )
                except Exception as exc:
                    err_text = f"工具调用失败: {exc}"
                    yield self._with_agent(
                        StreamChunk(
                            type="tool_call_error",
                            content=err_text,
                            tool_name=tc.name,
                            tool_call_id=tc.id,
                        )
                    )
                    tool_result = err_text

                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            logger.warning(
                "MCP 工具调用轮次达到上限 (%d)，将基于已有结果生成回答",
                self._settings.mcp_max_tool_rounds,
            )

        # 最终流式回答（含 reasoning）
        full_content = ""
        full_reasoning = ""
        async for chunk in self._llm.stream_chat(api_messages):
            if chunk.type == "reasoning":
                full_reasoning += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "content":
                full_content += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "error":
                yield self._with_agent(chunk)
                return
            elif chunk.type == "done":
                if chunk.usage:
                    usage = chunk.usage
                yield self._with_agent(
                    StreamChunk(type="done", content="", usage=usage)
                )
                return

        yield self._with_agent(StreamChunk(type="done", content="", usage=usage))

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
    ) -> AsyncIterator[StreamChunk]:
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt

        full_history = self._sessions.get_messages(sid)
        history = await self._memory.get_llm_context(
            sid,
            max_messages=max_history_messages,
            enable_summary=enable_history_summary,
        )

        use_tools = (
            self._settings.enable_mcp
            if enable_tools is None
            else enable_tools
        )
        mcp = await self._resolve_mcp() if use_tools else None
        tools = mcp.get_openai_tools() if mcp and mcp.is_connected else []
        effective_tools = use_tools and bool(tools)

        api_messages = self._build_messages(
            history,
            message,
            system_prompt,
            enable_tools=effective_tools,
        )

        logger.info(
            "Agent[%s] session=%s 全量历史=%d L1上下文=%d tools=%d",
            self.name,
            sid,
            len(full_history),
            len(history),
            len(tools),
        )

        full_content = ""
        full_reasoning = ""

        if effective_tools and mcp is not None:
            async for chunk in self._run_tool_loop(api_messages, tools, mcp):
                if chunk.type == "content":
                    full_content += chunk.content
                    yield chunk
                elif chunk.type == "reasoning":
                    full_reasoning += chunk.content
                    yield chunk
                elif chunk.type == "done":
                    self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                    self._sessions.append_message(
                        sid,
                        ChatMessage(
                            role="assistant",
                            content=full_content,
                            reasoning_content=full_reasoning or None,
                        ),
                    )
                    usage = chunk.usage or {}
                    usage["session_id"] = sid
                    yield self._with_agent(
                        StreamChunk(type="done", content="", usage=usage)
                    )
                    return
                elif chunk.type == "error":
                    yield chunk
                    return
                else:
                    yield chunk
            return

        async for chunk in self._llm.stream_chat(api_messages):
            if chunk.type == "reasoning":
                full_reasoning += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "content":
                full_content += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "error":
                yield self._with_agent(chunk)
                return
            elif chunk.type == "done":
                self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                self._sessions.append_message(
                    sid,
                    ChatMessage(
                        role="assistant",
                        content=full_content,
                        reasoning_content=full_reasoning or None,
                    ),
                )
                usage = chunk.usage or {}
                usage["session_id"] = sid
                yield self._with_agent(StreamChunk(type="done", content="", usage=usage))

    async def run_sync(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
    ) -> tuple[str, str, str, dict | None]:
        sid = self._sessions.get_or_create(session_id)
        content = ""
        reasoning = ""
        usage: dict | None = None

        async for chunk in self.run(
            message,
            sid,
            system_prompt_override=system_prompt_override,
            max_history_messages=max_history_messages,
            enable_history_summary=enable_history_summary,
            enable_tools=enable_tools,
        ):
            if chunk.type == "reasoning":
                reasoning += chunk.content
            elif chunk.type == "content":
                content += chunk.content
            elif chunk.type == "done":
                usage = chunk.usage

        return sid, content, reasoning or "", usage


_general_agent: GeneralAgent | None = None


def get_general_agent(*, math_mode: bool = False) -> GeneralAgent:
    global _general_agent
    if math_mode:
        return GeneralAgent(math_mode=True)
    if _general_agent is None:
        _general_agent = GeneralAgent(math_mode=False)
    return _general_agent

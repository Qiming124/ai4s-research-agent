# =============================================================================
# Agent 抽象基类与 GeneralAgent 实现。
#
# 职责：
#     BaseAgent    — 定义所有智能体的统一接口（抽象基类）
#     GeneralAgent — Phase 1 默认的通用科研助手
#
# 架构位置：
#     server/api/chat.py → GeneralAgent.run() / run_sync()
#     GeneralAgent       → MemoryManager（L1/L2）+ DeepSeekClient（调 LLM）
#
# Phase 2 扩展：
#     TheoryAgent / ExperimentAgent / LiteratureAgent 继承 BaseAgent，
#     通过 LangGraph router 按用户意图分发。
#
# Debug：
#     - 响应很慢：v4-pro + reasoning_effort=max 本身需要几十秒，正常
#     - 历史过长：调整 MAX_HISTORY_MESSAGES / ENABLE_HISTORY_SUMMARY
# =============================================================================

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from server.config import Settings, get_settings
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.llm.prompts import DEFAULT_SYSTEM_PROMPT, MATH_MODE_SYSTEM_PROMPT
from server.memory.base import BaseSessionStore
from server.memory.manager import MemoryManager, get_memory_manager
from server.memory.session import SessionStore, get_session_store
from shared.schemas import ChatMessage, StreamChunk

logger = logging.getLogger(__name__)


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
        *,
        math_mode: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm_client or get_deepseek_client()
        self._sessions: BaseSessionStore = session_store or get_session_store()
        self._memory = memory_manager or get_memory_manager()
        self.system_prompt = MATH_MODE_SYSTEM_PROMPT if math_mode else self._settings.default_system_prompt

    def _with_agent(self, chunk: StreamChunk) -> StreamChunk:
        return chunk.model_copy(update={"agent_name": self.name})

    def _build_messages(
        self,
        history: list[ChatMessage],
        user_message: str,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
    ) -> AsyncIterator[StreamChunk]:
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt

        full_history = self._sessions.get_messages(sid)
        history = await self._memory.get_llm_context(
            sid,
            max_messages=max_history_messages,
            enable_summary=enable_history_summary,
        )
        api_messages = self._build_messages(history, message, system_prompt)

        logger.info(
            "Agent[%s] session=%s 全量历史=%d L1上下文=%d",
            self.name,
            sid,
            len(full_history),
            len(history),
        )

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
                self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                self._sessions.append_message(
                    sid,
                    ChatMessage(
                        role="assistant",
                        content=full_content,
                        reasoning_content=full_reasoning or None,
                    ),
                )
                logger.debug(
                    "Agent[%s] session=%s done — reasoning=%d字 content=%d字",
                    self.name,
                    sid,
                    len(full_reasoning),
                    len(full_content),
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
    ) -> tuple[str, str, str, dict | None]:
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt
        history = await self._memory.get_llm_context(
            sid,
            max_messages=max_history_messages,
            enable_summary=enable_history_summary,
        )
        api_messages = self._build_messages(history, message, system_prompt)

        content, reasoning, usage = await self._llm.chat(api_messages)

        self._sessions.append_message(sid, ChatMessage(role="user", content=message))
        self._sessions.append_message(
            sid,
            ChatMessage(
                role="assistant",
                content=content,
                reasoning_content=reasoning or None,
            ),
        )

        return sid, content, reasoning or "", usage


_general_agent: GeneralAgent | None = None


def get_general_agent(*, math_mode: bool = False) -> GeneralAgent:
    global _general_agent
    if math_mode:
        return GeneralAgent(math_mode=True)
    if _general_agent is None:
        _general_agent = GeneralAgent(math_mode=False)
    return _general_agent

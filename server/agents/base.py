"""
Agent 抽象基类与 General Agent 实现。

职责：
    - BaseAgent：定义所有智能体的统一接口（Phase 2 扩展 Theory/Experiment/Literature）
    - GeneralAgent：Phase 1 默认通用科研助手

架构位置：
    server/api/chat.py → GeneralAgent.run()
    GeneralAgent → SessionStore + DeepSeekClient

类比 C++：
    BaseAgent 类似纯虚基类 IAgent，GeneralAgent 是具体实现。
    Phase 2 可用工厂模式或 router 按意图选择子类。

Debug：
    - 响应慢：v4-pro + reasoning max 本身耗时较长，属正常现象
    - 上下文过长：Phase 1 全量传历史，注意 token 成本
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from server.config import Settings, get_settings
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.llm.prompts import DEFAULT_SYSTEM_PROMPT, MATH_MODE_SYSTEM_PROMPT
from server.memory.session import SessionStore, get_session_store
from shared.schemas import ChatMessage, StreamChunk

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    智能体抽象基类。

    子类必须实现 run() 方法。Phase 2 将添加：
        - TheoryAgent：理论推导专用
        - ExperimentAgent：实验诊断专用
        - LiteratureAgent：文献检索专用
    """

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
        """
        处理用户消息并流式返回结果。

        Args:
            message: 用户输入
            session_id: 会话 ID，None 时自动创建
            system_prompt_override: 可选覆盖 system prompt

        Yields:
            StreamChunk 流
        """
        ...  # pragma: no cover


class GeneralAgent(BaseAgent):
    """
    通用科研助手 Agent（Phase 1 默认实现）。

    流程：
        1. 获取/创建 session_id
        2. 从 SessionStore 读取历史
        3. 构造 messages（system + history + 新 user 消息）
        4. 调用 DeepSeekClient.stream_chat
        5. 流结束后将 user/assistant 消息写回 SessionStore
    """

    name = "general"

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: DeepSeekClient | None = None,
        session_store: SessionStore | None = None,
        *,
        math_mode: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm_client or get_deepseek_client()
        self._sessions = session_store or get_session_store()
        # math_mode 使用更形式化的 system prompt
        self.system_prompt = MATH_MODE_SYSTEM_PROMPT if math_mode else self._settings.default_system_prompt

    def _build_messages(
        self,
        history: list[ChatMessage],
        user_message: str,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        """
        将 SessionStore 中的历史 + 新消息 转为 OpenAI API 格式。

        结构：[system] + [历史 user/assistant 交替] + [新 user]

        Phase 2 可在此加入 max_history_messages 截断或 summarization。
        """
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # 若配置了历史条数上限，只保留最近 N 条
        max_hist = self._settings.max_history_messages
        trimmed = history[-max_hist:] if max_hist > 0 else history

        for msg in trimmed:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        执行一轮对话（流式）。

        注意：本方法在流式 yield 完成后才写入 assistant 消息到 SessionStore，
        这样若中途出错，不会污染历史。
        """
        # Step 1: 确保 session 存在
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt

        # Step 2: 读取历史（不含本轮 user 消息）
        history = self._sessions.get_messages(sid)

        # Step 3: 构造 API messages
        api_messages = self._build_messages(history, message, system_prompt)

        logger.info("Agent[%s] session=%s 历史=%d 条", self.name, sid, len(history))

        # 累积完整回答，流结束后写入 session
        full_content = ""
        full_reasoning = ""

        async for chunk in self._llm.stream_chat(api_messages):
            if chunk.type == "reasoning":
                full_reasoning += chunk.content
                yield chunk
            elif chunk.type == "content":
                full_content += chunk.content
                yield chunk
            elif chunk.type == "error":
                yield chunk
                return
            elif chunk.type == "done":
                # Step 4: 流成功结束，持久化到 SessionStore
                self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                self._sessions.append_message(
                    sid,
                    ChatMessage(role="assistant", content=full_content),
                )
                logger.debug(
                    "Agent[%s] session=%s 已保存，reasoning 长度=%d，content 长度=%d",
                    self.name,
                    sid,
                    len(full_reasoning),
                    len(full_content),
                )
                # 在 done chunk 的 usage 中附加 session_id 供 API 层使用
                usage = chunk.usage or {}
                usage["session_id"] = sid
                yield StreamChunk(type="done", content="", usage=usage)

    async def run_sync(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
    ) -> tuple[str, str, str, dict | None]:
        """
        非流式执行一轮对话（供 POST /v1/chat 使用）。

        Returns:
            (session_id, content, reasoning, usage)
        """
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt
        history = self._sessions.get_messages(sid)
        api_messages = self._build_messages(history, message, system_prompt)

        content, reasoning, usage = await self._llm.chat(api_messages)

        self._sessions.append_message(sid, ChatMessage(role="user", content=message))
        self._sessions.append_message(sid, ChatMessage(role="assistant", content=content))

        return sid, content, reasoning or "", usage


# 默认 Agent 单例
_general_agent: GeneralAgent | None = None


def get_general_agent(*, math_mode: bool = False) -> GeneralAgent:
    """获取 GeneralAgent 实例。"""
    global _general_agent
    if math_mode or _general_agent is None:
        return GeneralAgent(math_mode=math_mode)
    return _general_agent

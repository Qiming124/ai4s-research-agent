# =============================================================================
# Agent 抽象基类与 GeneralAgent 实现。
#
# 职责：
#     BaseAgent    — 定义所有智能体的统一接口（抽象基类）
#     GeneralAgent — Phase 1 默认的通用科研助手
#
# 架构位置：
#     server/api/chat.py → GeneralAgent.run() / run_sync()
#     GeneralAgent       → 调用 SessionStore（读写历史）+ DeepSeekClient（调 LLM）
#
# Phase 2 扩展：
#     TheoryAgent / ExperimentAgent / LiteratureAgent 继承 BaseAgent，
#     通过 LangGraph router 按用户意图分发。
#
# Debug：
#     - 响应很慢：v4-pro + reasoning_effort=max 本身需要几十秒，正常
#     - 历史过长：Phase 1 全量传入历史；Phase 2 加摘要/截断
# =============================================================================

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
    # 所有智能体的抽象基类。
    #
    # 子类必须实现：
    #     async def run(self, message, session_id, *, system_prompt_override=None) -> AsyncIterator[StreamChunk]
    #
    # Phase 2 将扩展：
    #     TheoryAgent     — 理论推导（复杂不等式、边界条件、有界性证明）
    #     ExperimentAgent — 实验诊断（训练曲线异常、超参分析）
    #     LiteratureAgent — 文献检索（论文总结、证明范式对照）

    name: str = "base"                           # Agent 标识名，用于日志区分
    system_prompt: str = DEFAULT_SYSTEM_PROMPT    # 默认系统提示词，子类可覆盖

    @abstractmethod
    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        # 处理用户消息并流式返回结果（子类必须实现）。
        #
        # 参数：
        #     message                — 用户输入文本
        #     session_id             — 会话 ID；None 时子类自行创建（通常委托 SessionStore）
        #     system_prompt_override — 可选：本轮对话临时覆盖的 system prompt
        #
        # 返回 AsyncIterator[StreamChunk]，调用方用 async for 逐块消费。
        ...


class GeneralAgent(BaseAgent):
    # 通用科研助手 Agent（Phase 1 默认实现）。
    #
    # run() 流程：
    #     1. 从 SessionStore 获取/创建 session_id
    #     2. 读取该会话的历史消息
    #     3. 构造 API 消息列表：[system, ...历史, 新 user]
    #     4. 调用 DeepSeekClient.stream_chat() 发起流式请求
    #     5. 逐 chunk 转发给调用方
    #     6. 流结束后把 user 和 assistant 消息写回 SessionStore
    #
    # run_sync() 流程同上，但使用非流式 chat() 一次性等完响应。
    #
    # 系统提示词选择规则：
    #     math_mode=True  → MATH_MODE_SYSTEM_PROMPT（严格数学推导）
    #     math_mode=False → Settings.default_system_prompt（通用科研助手）

    name = "general"

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: DeepSeekClient | None = None,
        session_store: SessionStore | None = None,
        *,
        math_mode: bool = False,
    ) -> None:
        # 初始化 GeneralAgent。
        #
        # 参数：
        #     settings      — 配置；None 时用全局 get_settings()
        #     llm_client    — DeepSeek 客户端；None 时用全局单例
        #     session_store — 会话仓库；None 时用全局单例
        #     math_mode     — True 时使用数学推导专用 prompt
        self._settings = settings or get_settings()
        self._llm = llm_client or get_deepseek_client()
        self._sessions = session_store or get_session_store()
        self.system_prompt = MATH_MODE_SYSTEM_PROMPT if math_mode else self._settings.default_system_prompt

    def _build_messages(
        self,
        history: list[ChatMessage],
        user_message: str,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        # 将历史消息 + 新用户输入 + 系统提示词拼装成 OpenAI API 格式。
        #
        # 参数：
        #     history       — 从 SessionStore 读取的历史 ChatMessage 列表
        #     user_message  — 用户本轮输入
        #     system_prompt — 系统提示词文本
        #
        # 返回 list[dict]，格式 [{"role":"system",...}, {"role":"user",...}, ...]
        #
        # 拼接规则：
        #     1. 第一条 role=system
        #     2. 中间历史消息原样追加
        #     3. 最后 role=user
        #
        # 若 Settings.max_history_messages > 0，只保留最近 N 条历史。
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

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
        # 执行一轮对话（流式模式）。
        #
        # 参数：
        #     message                — 用户输入文本
        #     session_id             — 会话 ID；None 时由 SessionStore 自动创建
        #     system_prompt_override — 临时 system prompt（优先级高于构造时默认值）
        #
        # 产出 StreamChunk（reasoning / content / done / error 四种 type）。
        #
        # 重要设计：只有流成功结束（done）后才写入 SessionStore。
        #           中途 error 则直接 return，不污染历史。
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt

        history = self._sessions.get_messages(sid)
        api_messages = self._build_messages(history, message, system_prompt)

        logger.info("Agent[%s] session=%s 历史消息数=%d", self.name, sid, len(history))

        # 累积完整文本，用于流结束后写入 SessionStore
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
                return    # 出错不写历史
            elif chunk.type == "done":
                # 流成功结束 → 持久化 user + assistant 消息
                self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                self._sessions.append_message(
                    sid,
                    ChatMessage(role="assistant", content=full_content),
                )
                logger.debug(
                    "Agent[%s] session=%s done — reasoning=%d字 content=%d字",
                    self.name, sid, len(full_reasoning), len(full_content),
                )
                # session_id 附加到 done chunk 的 usage 中，供 API 层使用
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
        # 执行一轮对话（非流式模式，POST /v1/chat 使用）。
        #
        # 参数同 run()。
        #
        # 返回 (session_id, content, reasoning, usage) 四部组：
        #     session_id — 会话 ID
        #     content    — 模型回答文本
        #     reasoning  — 思考过程（可能为空字符串）
        #     usage      — token 用量字典（可能为 None）
        #
        # 内部调用 DeepSeekClient.chat()（非流式），同样遵循"成功才写入"原则。
        sid = self._sessions.get_or_create(session_id)
        system_prompt = system_prompt_override or self.system_prompt
        history = self._sessions.get_messages(sid)
        api_messages = self._build_messages(history, message, system_prompt)

        content, reasoning, usage = await self._llm.chat(api_messages)

        self._sessions.append_message(sid, ChatMessage(role="user", content=message))
        self._sessions.append_message(sid, ChatMessage(role="assistant", content=content))

        return sid, content, reasoning or "", usage


# ── 默认 Agent 实例 ─────────────────────────────────────────

_general_agent: GeneralAgent | None = None


def get_general_agent(*, math_mode: bool = False) -> GeneralAgent:
    # 获取 GeneralAgent 实例。
    #
    # 参数 math_mode=True 时新建数学推导模式 Agent（不影响缓存的默认实例）。
    # 后续 math_mode=False 调用返回缓存实例。
    global _general_agent
    if math_mode or _general_agent is None:
        return GeneralAgent(math_mode=math_mode)
    return _general_agent

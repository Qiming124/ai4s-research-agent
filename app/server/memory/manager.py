# =============================================================================
# MemoryManager：L2 读取 + L1 处理的统一入口。
#
# Phase 2A 轻量实现，供 GeneralAgent 及后续 Phase 2B+ 扩展使用。
# =============================================================================

from __future__ import annotations

from server.config import Settings, get_settings
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.memory.base import BaseSessionStore
from server.memory.session import get_session_store
from server.memory.working import prepare_history_for_llm
from shared.schemas import ChatMessage

_manager: MemoryManager | None = None


class MemoryManager:
    """
    L2 读取 + L1 处理统一入口。

    职责：
        - get_full_history(): 从 SessionStore 获取完整 L2 历史
        - get_llm_context():  应用 L1 截断/摘要策略后返回给 Agent

    被 GeneralAgent / SubAgent 调用，不直接对外暴露 HTTP API。
    """

    def __init__(
        self,
        store: BaseSessionStore,
        settings: Settings,
        llm: DeepSeekClient,
    ) -> None:
        """
        参数:
            store: L2 会话存储后端（memory 或 sqlite）
            settings: 运行时配置
            llm: DeepSeek 客户端（供摘要生成用）
        """
        self._store = store
        self._settings = settings
        self._llm = llm

    def get_full_history(self, session_id: str) -> list[ChatMessage]:
        """获取 L2 完整会话历史（不做截断/摘要）。"""
        return self._store.get_messages(session_id)

    async def get_llm_context(
        self,
        session_id: str,
        *,
        max_messages: int | None = None,
        enable_summary: bool | None = None,
    ) -> list[ChatMessage]:
        """
        获取注入 LLM 的上下文消息列表（含 L1 截断与可能摘要）。

        参数:
            session_id: 会话 ID
            max_messages: L1 保留最近 N 条；None=使用 .env 默认值
            enable_summary: 截断时是否 LLM 摘要；None=使用 .env 默认值

        返回:
            处理后的 ChatMessage 列表
        """
        raw = self._store.get_messages(session_id)
        effective_max = (
            self._settings.max_history_messages
            if max_messages is None
            else max_messages
        )
        effective_summary = (
            self._settings.enable_history_summary
            if enable_summary is None
            else enable_summary
        )
        return await prepare_history_for_llm(
            raw,
            max_messages=effective_max,
            enable_summary=effective_summary,
            llm=self._llm,
            summary_max_tokens=self._settings.history_summary_max_tokens,
        )


def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        settings = get_settings()
        _manager = MemoryManager(
            store=get_session_store(),
            settings=settings,
            llm=get_deepseek_client(),
        )
    return _manager


def reset_memory_manager() -> None:
    global _manager
    _manager = None

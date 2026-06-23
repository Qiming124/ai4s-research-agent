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
    def __init__(
        self,
        store: BaseSessionStore,
        settings: Settings,
        llm: DeepSeekClient,
    ) -> None:
        self._store = store
        self._settings = settings
        self._llm = llm

    def get_full_history(self, session_id: str) -> list[ChatMessage]:
        return self._store.get_messages(session_id)

    async def get_llm_context(
        self,
        session_id: str,
        *,
        max_messages: int | None = None,
        enable_summary: bool | None = None,
    ) -> list[ChatMessage]:
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

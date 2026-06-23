# =============================================================================
# 会话存储模块（内存后端 + 工厂函数）。
#
# 职责：维护 session_id → 消息列表 的映射，支持多轮对话上下文记忆。
#
# 架构位置：
#     server/agents/base.py → GeneralAgent.run() / run_sync() 读写会话
#     server/api/chat.py    → GET/POST/DELETE /v1/sessions/* 操作会话
#
# Phase 2A：
#     InMemorySessionStore — 纯内存（SESSION_STORE_BACKEND=memory）
#     SQLiteSessionStore   — SQLite 持久化（默认，见 sqlite_store.py）
#     get_session_store()  — 按配置返回对应后端单例
#
# Debug：
#     - 多轮对话无上下文 → 检查 session_id 是否各轮保持一致
#     - 重启后会话丢失   → 确认 SESSION_STORE_BACKEND=sqlite
# =============================================================================

from __future__ import annotations

import uuid
from copy import deepcopy

from server.config import get_settings
from server.memory.base import BaseSessionStore
from shared.schemas import ChatMessage


class InMemorySessionStore(BaseSessionStore):
    # 基于内存字典的会话仓库（Phase 1 实现，进程重启数据丢失）。

    def __init__(self) -> None:
        self._sessions: dict[str, list[ChatMessage]] = {}

    def create_session_id(self) -> str:
        return str(uuid.uuid4())

    def get_or_create(self, session_id: str | None) -> str:
        if not session_id:
            session_id = self.create_session_id()
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return session_id

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        messages = self._sessions.get(session_id, [])
        return deepcopy(messages)

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    def clear_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        self._sessions[session_id] = []
        return True

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def list_session_ids(self) -> list[str]:
        return list(self._sessions.keys())


# Phase 1 类名别名，保持 agents/base.py 等调用方 import 不变
SessionStore = InMemorySessionStore


# ── 全局单例 ────────────────────────────────────────────────

_session_store: BaseSessionStore | None = None


def get_session_store() -> BaseSessionStore:
    # 获取全局会话仓库单例；按 SESSION_STORE_BACKEND 选择 memory 或 sqlite 后端。
    global _session_store
    if _session_store is None:
        settings = get_settings()
        if settings.session_store_backend == "sqlite":
            from server.memory.sqlite_store import SQLiteSessionStore

            _session_store = SQLiteSessionStore(settings.session_db_path)
        else:
            _session_store = InMemorySessionStore()
    return _session_store


def reset_session_store() -> None:
    # 清除全局单例（仅供测试使用，避免测试间状态污染）。
    global _session_store
    _session_store = None

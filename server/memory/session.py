# =============================================================================
# 内存会话存储模块。
#
# 职责：在进程内存中维护 session_id → 消息列表 的映射字典，支持多轮对话的上下文记忆。
#
# 架构位置：
#     server/agents/base.py → GeneralAgent.run() / run_sync() 读写会话
#     server/api/chat.py    → GET/POST/DELETE /v1/sessions/* 操作会话
#
# 内部存储：dict[str, list[ChatMessage]]
#     键 = session_id（UUID 字符串）
#     值 = ChatMessage 列表（按时间顺序，user/assistant 交替）
#
# Phase 1 局限：
#     1. 进程重启会话丢失（纯内存无持久化）
#     2. 多 worker 部署时各持一份独立存储（Phase 2 计划换 SQLite/Redis）
#
# Debug：
#     - 多轮对话无上下文 → 检查 session_id 是否各轮保持一致
#     - 历史突然为空   → uvicorn --reload 或重启会清空内存，正常现象
# =============================================================================

from __future__ import annotations

import uuid
from copy import deepcopy

from shared.schemas import ChatMessage


class SessionStore:
    # 基于内存字典的会话仓库。
    #
    # 典型用法：
    #     store = SessionStore()
    #     sid = store.get_or_create("my-session")
    #     store.append_message(sid, msg)
    #     messages = store.get_messages(sid)
    #     store.clear_session(sid)

    def __init__(self) -> None:
        # 初始化空会话仓库。内部结构：
        # self._sessions = {"uuid": [ChatMessage(...), ...], ...}
        self._sessions: dict[str, list[ChatMessage]] = {}

    def create_session_id(self) -> str:
        # 生成新的 UUID 会话 ID。每次调用保证全局唯一。
        # 返回格式：a1b2c3d4-e5f6-7890-abcd-ef1234567890
        return str(uuid.uuid4())

    def get_or_create(self, session_id: str | None) -> str:
        # 根据传入值获取或创建会话。
        #
        # 参数 session_id — 客户端指定的会话 ID；None 时自动生成。
        #
        # 返回实际使用的 session_id。
        #
        # 行为：
        #     session_id 已存在 → 直接返回
        #     session_id 不存在 → 在字典中创建空列表后返回
        #     session_id 为 None → 调用 create_session_id() 生成
        if not session_id:
            session_id = self.create_session_id()
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return session_id

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        # 获取指定会话的全部历史消息（返回深拷贝）。
        #
        # 返回深拷贝的原因：防止调用方拿到内部列表引用后直接修改，绕开 append_message。
        # 若会话不存在，返回空列表。
        messages = self._sessions.get(session_id, [])
        return deepcopy(messages)

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        # 向指定会话追加一条消息。
        # 若 session_id 尚未创建，自动创建空列表后再追加。
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    def clear_session(self, session_id: str) -> bool:
        # 清空指定会话的全部历史消息（保留 session_id 本身）。
        #
        # 若会话存在并被清空返回 True ；若不存在返回 False。
        #
        # 与 delete_session 区别：clear 只清空列表留 key，delete 直接删 key。
        if session_id not in self._sessions:
            return False
        self._sessions[session_id] = []
        return True

    def delete_session(self, session_id: str) -> bool:
        # 完全删除指定会话（从字典移除 key）。
        # 若会话存在且被删除返回 True ；若不存在返回 False。
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        # 检查指定会话是否存在（即使消息列表为空也返回 True）。
        return session_id in self._sessions

    def list_session_ids(self) -> list[str]:
        # 列出当前所有会话 ID（调试用，生产环境少用）。
        return list(self._sessions.keys())


# ── 全局单例 ────────────────────────────────────────────────

_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    # 获取全局会话仓库单例。
    # 首次调用时创建，后续返回同一对象（整个 FastAPI 进程共享）。
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store

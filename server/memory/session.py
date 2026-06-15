"""
内存会话存储模块。

职责：
    在进程内存中维护 session_id → 消息列表 的映射，支持多轮对话上下文。

架构位置：
    server/agents/general.py 读写会话
    server/api/chat.py 暴露 GET/DELETE 会话接口

类比 C++：
    std::unordered_map<std::string, std::vector<ChatMessage>> sessions_;

Phase 1 局限：
    - 进程重启后会话丢失
    - 无并发锁（asyncio 单线程事件循环下通常安全，但多 worker 部署会各持一份）
    Phase 2 可替换为 SQLite / Redis 并加 asyncio.Lock。

Debug：
    - 多轮对话无上下文：检查 session_id 是否在请求中保持一致
    - 会话莫名消失：uvicorn --reload 或重启会清空内存
"""

from __future__ import annotations

import uuid
from copy import deepcopy

from shared.schemas import ChatMessage


class SessionStore:
    """
    内存会话仓库。

    内部结构：dict[session_id, list[ChatMessage]]
    """

    def __init__(self) -> None:
        # 类比 C++: std::unordered_map<std::string, std::vector<ChatMessage>>
        self._sessions: dict[str, list[ChatMessage]] = {}

    def create_session_id(self) -> str:
        """生成新的 UUID 格式 session_id。"""
        return str(uuid.uuid4())

    def get_or_create(self, session_id: str | None) -> str:
        """
        若 session_id 为空则创建新会话；否则确保该 ID 在 store 中存在。

        Returns:
            实际使用的 session_id
        """
        if not session_id:
            session_id = self.create_session_id()
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return session_id

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        """
        获取会话历史（返回副本，避免外部直接修改内部列表）。

        Debug：
            若返回空列表，可能是新会话或已被 clear。
        """
        messages = self._sessions.get(session_id, [])
        return deepcopy(messages)

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        """向会话追加一条消息。"""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    def clear_session(self, session_id: str) -> bool:
        """
        清空指定会话的消息历史。

        Returns:
            True 若会话存在并被清空；False 若会话不存在
        """
        if session_id not in self._sessions:
            return False
        self._sessions[session_id] = []
        return True

    def delete_session(self, session_id: str) -> bool:
        """
        完全删除会话条目。

        Returns:
            True 若会话存在并被删除
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在。"""
        return session_id in self._sessions

    def list_session_ids(self) -> list[str]:
        """列出所有 session_id（调试用）。"""
        return list(self._sessions.keys())


# 全局单例：整个 FastAPI 进程共享同一份会话存储
_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """获取 SessionStore 单例。"""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store

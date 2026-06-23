# =============================================================================
# 会话存储抽象基类。
#
# 职责：定义所有 SessionStore 后端必须实现的 8 个方法契约。
#
# 实现：
#     InMemorySessionStore — Phase 1 内存 dict（server/memory/session.py）
#     SQLiteSessionStore   — Phase 2A SQLite 持久化（server/memory/sqlite_store.py）
#
# 调用方通过 get_session_store() 获取实例，不应直接实例化具体后端。
# =============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.schemas import ChatMessage


class BaseSessionStore(ABC):
    """
    会话仓库抽象基类——子类必须实现 8 个方法。

    方法契约：

        1. create_session_id() → str
           生成新的 UUID 会话 ID。

        2. get_or_create(session_id?: str) → str
           获取或创建会话。session_id 为 None 时自动生成。

        3. get_messages(session_id: str) → list[ChatMessage]
           获取指定会话的全部历史消息。返回副本防止外部修改。
           会话不存在时返回空列表。

        4. append_message(session_id: str, message: ChatMessage) → None
           向指定会话追加一条消息。session 不存在时自动创建。

        5. clear_session(session_id: str) → bool
           清空指定会话的消息列表（保留 session_id 本身）。
           返回 True 若会话存在；False 若不存在。

        6. delete_session(session_id: str) → bool
           完全删除会话及所有消息。
           返回 True 若会话存在并已删除；False 若不存在。

        7. session_exists(session_id: str) → bool
           检查会话是否存在（即使消息列表为空也返回 True）。

        8. list_session_ids() → list[str]
           列出当前所有会话 ID（调试用，按创建时间排列）。
    """

    @abstractmethod
    def create_session_id(self) -> str:
        ...

    @abstractmethod
    def get_or_create(self, session_id: str | None) -> str:
        ...

    @abstractmethod
    def get_messages(self, session_id: str) -> list[ChatMessage]:
        ...

    @abstractmethod
    def append_message(self, session_id: str, message: ChatMessage) -> None:
        ...

    @abstractmethod
    def clear_session(self, session_id: str) -> bool:
        ...

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        ...

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        ...

    @abstractmethod
    def list_session_ids(self) -> list[str]:
        ...

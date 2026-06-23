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
    # 会话仓库抽象基类。子类必须实现以下 8 个方法。

    @abstractmethod
    def create_session_id(self) -> str:
        # 生成新的 UUID 会话 ID。
        # 返回：全局唯一的 session_id 字符串。
        ...

    @abstractmethod
    def get_or_create(self, session_id: str | None) -> str:
        # 获取或创建会话。
        # 参数 session_id — 客户端指定 ID；None 时自动生成。
        # 返回：实际使用的 session_id。
        ...

    @abstractmethod
    def get_messages(self, session_id: str) -> list[ChatMessage]:
        # 获取指定会话的全部历史消息（返回副本，防止外部修改内部状态）。
        # 参数 session_id — 目标会话 ID。
        # 返回：按时间顺序排列的 ChatMessage 列表；会话不存在时返回空列表。
        ...

    @abstractmethod
    def append_message(self, session_id: str, message: ChatMessage) -> None:
        # 向指定会话追加一条消息；session 不存在时自动创建。
        # 参数 session_id — 目标会话 ID。
        # 参数 message    — 要追加的消息。
        ...

    @abstractmethod
    def clear_session(self, session_id: str) -> bool:
        # 清空指定会话的全部历史消息（保留 session_id 本身）。
        # 返回：会话存在并已清空 True；不存在 False。
        ...

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        # 完全删除指定会话（含所有消息）。
        # 返回：会话存在并已删除 True；不存在 False。
        ...

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        # 检查指定会话是否存在（即使消息列表为空也返回 True）。
        ...

    @abstractmethod
    def list_session_ids(self) -> list[str]:
        # 列出当前所有会话 ID（调试用）。
        ...

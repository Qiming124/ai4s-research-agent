# =============================================================================
# server.memory 包：会话与长期记忆层。
#
# Phase 2A：
#     base.py        — BaseSessionStore 抽象基类
#     session.py     — InMemorySessionStore + get_session_store() 工厂
#     sqlite_store.py — SQLiteSessionStore 持久化（L2 Session Memory）
#     working.py     — L1 历史截断与可选 LLM 摘要
#     manager.py     — MemoryManager 统一入口
#
# Phase 3-4：
#     rag/           — L3 RAG 向量库（Phase 5）
#     structured/    — L4 结构化科研记忆
# =============================================================================

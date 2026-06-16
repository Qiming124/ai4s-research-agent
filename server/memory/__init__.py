# =============================================================================
# server.memory 包：会话与长期记忆层。
#
# Phase 2A：
#     base.py        — BaseSessionStore 抽象基类
#     session.py     — InMemorySessionStore + get_session_store() 工厂
#     sqlite_store.py — SQLiteSessionStore 持久化（L2 Session Memory）
#
# Phase 2A 后续 / Phase 3-4：
#     working.py     — L1 Working Memory 截断/摘要
#     semantic/      — L3 RAG 向量库
#     structured/    — L4 结构化科研记忆
# =============================================================================

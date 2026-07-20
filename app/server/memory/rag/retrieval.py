# =============================================================================
# RAG 检索与上下文注入。
#
# 职责：
#     1. retrieve_for_query() 向量检索 top-k 片段
#     2. format_rag_context() / build_rag_augmented_prompt() 注入 system prompt
#     3. 记录 SessionRagRef 供前端展示引用轨迹
#
# 架构位置：
#     - 被调用：server/agents/base.py、subagent.py、mcp/servers/rag.py
#     - 调用：memory/rag/store.py、session_refs.py
#
# 阅读提示：
#     - 新人先看 retrieve_for_query 与 build_rag_augmented_prompt
#
# Debug：
#     - 无片段 → ENABLE_RAG 或 namespace 无文档
#     - 引用不显示 → SessionRagRefStore 未写入
# =============================================================================

from __future__ import annotations

from server.config import Settings, get_settings
from server.memory.rag.session_refs import SessionRagRefStore
from server.memory.rag.store import RetrievedSnippet, get_rag_store, resolve_rag_project_id


def format_rag_context(snippets: list[RetrievedSnippet]) -> str:
    """将检索片段格式化为可注入 system prompt 的文本。"""
    if not snippets:
        return ""

    lines = [
        "以下是与用户问题相关的**本课题**知识库片段（请结合这些内容回答，并注明来源文档标题）：",
    ]
    for idx, snip in enumerate(snippets, start=1):
        header = f"[{idx}] {snip.title}"
        if snip.source:
            header += f" ({snip.source})"
        lines.append(header)
        lines.append(snip.content)
        lines.append("")
    return "\n".join(lines).strip()


def retrieve_for_query(
    query: str,
    settings: Settings | None = None,
    *,
    session_id: str,
    top_k: int | None = None,
    project_id: str | None = None,
) -> list[RetrievedSnippet]:
    cfg = settings or get_settings()
    session_id = session_id.strip()
    if not cfg.enable_rag or not session_id:
        return []

    pid = resolve_rag_project_id(session_id=session_id, project_id=project_id)
    store = get_rag_store()
    store.ensure_mcp_files_indexed(session_id, project_id=pid)
    return store.retrieve(query, session_id=session_id, project_id=pid, top_k=top_k)


def record_session_refs(
    session_id: str,
    snippets: list[RetrievedSnippet],
    settings: Settings | None = None,
) -> None:
    """将会话检索到的 doc 引用写入 SQLite（不含完整 chunk 正文）。"""
    if not snippets:
        return
    cfg = settings or get_settings()
    store = SessionRagRefStore(cfg.session_db_path)
    for snip in snippets:
        store.add_ref(session_id, snip.doc_id, snip.content)


def build_rag_augmented_prompt(
    base_prompt: str,
    query: str,
    session_id: str,
    settings: Settings | None = None,
    *,
    project_id: str | None = None,
) -> str:
    """检索 + 注入上下文 + 记录会话引用（课题共享语料）。"""
    cfg = settings or get_settings()
    if not cfg.enable_rag:
        return base_prompt

    snippets = retrieve_for_query(
        query, cfg, session_id=session_id, project_id=project_id,
    )
    if not snippets:
        return base_prompt

    record_session_refs(session_id, snippets, cfg)
    context = format_rag_context(snippets)
    return f"{base_prompt}\n\n{context}"

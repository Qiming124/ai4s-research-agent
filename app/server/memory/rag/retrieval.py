# RAG 检索与上下文注入（按 session_id 隔离）。

from __future__ import annotations

from server.config import Settings, get_settings
from server.memory.rag.session_refs import SessionRagRefStore
from server.memory.rag.store import RetrievedSnippet, get_rag_store


def format_rag_context(snippets: list[RetrievedSnippet]) -> str:
    """将检索片段格式化为可注入 system prompt 的文本。"""
    if not snippets:
        return ""

    lines = [
        "以下是与用户问题相关的**本会话**知识库片段（请结合这些内容回答，并注明来源文档标题）：",
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
) -> list[RetrievedSnippet]:
    cfg = settings or get_settings()
    session_id = session_id.strip()
    if not cfg.enable_rag or not session_id:
        return []

    store = get_rag_store()
    store.ensure_mcp_files_indexed(session_id)
    return store.retrieve(query, session_id=session_id, top_k=top_k)


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
) -> str:
    """检索 + 注入上下文 + 记录会话引用（仅当前 session 文档）。"""
    cfg = settings or get_settings()
    if not cfg.enable_rag:
        return base_prompt

    snippets = retrieve_for_query(query, cfg, session_id=session_id)
    if not snippets:
        return base_prompt

    record_session_refs(session_id, snippets, cfg)
    context = format_rag_context(snippets)
    return f"{base_prompt}\n\n{context}"

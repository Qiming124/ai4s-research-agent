# L4 结构化记忆注入：将定理/假设写入 system prompt。

from __future__ import annotations

from server.config import Settings, get_settings
from server.memory.structured.store import StructuredMemoryStore
from server.memory.theory_workspace import format_workspace_context


def format_structured_context(entries: list[dict]) -> str:
    """将结构化记忆条目格式化为可注入 system prompt 的文本。"""
    if not entries:
        return ""

    lines = [
        "以下是本会话已记录的结构化科研记忆（引理/假设/定理等），推导时请保持一致并引用编号：",
    ]
    for idx, entry in enumerate(entries, start=1):
        kind = entry.get("kind", "note")
        title = entry.get("title", "")
        body = entry.get("body", "")
        header = f"[{idx}] ({kind})"
        if title:
            header += f" {title}"
        lines.append(header)
        lines.append(body)
        lines.append("")
    return "\n".join(lines).strip()


def build_structured_augmented_prompt(
    base_prompt: str,
    session_id: str | None,
    agent_name: str,
    settings: Settings | None = None,
    *,
    kinds: tuple[str, ...] = ("theorem", "hypothesis", "note"),
    limit: int = 20,
) -> str:
    """检索 L4 记忆并注入 system prompt。"""
    cfg = settings or get_settings()
    allowed = cfg.structured_memory_agent_names()
    if allowed and agent_name not in allowed:
        return base_prompt

    parts = [base_prompt]
    if agent_name in ("theory", "review"):
        workspace_ctx = format_workspace_context(cfg)
        if workspace_ctx:
            parts.append(workspace_ctx)
    if agent_name == "review":
        from server.memory.theory_workspace import load_review_checklist
        checklist = load_review_checklist(cfg)
        if checklist:
            parts.append("### 审稿清单\n" + checklist)

    if not session_id:
        return "\n\n".join(parts) if len(parts) > 1 else base_prompt

    store = StructuredMemoryStore(cfg.session_db_path)
    entries: list[dict] = []
    for kind in kinds:
        entries.extend(
            store.list_entries(session_id=session_id, kind=kind, limit=limit)
        )
    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    entries = entries[:limit]

    context = format_structured_context(entries)
    if context:
        parts.append(context)
    if len(parts) == 1:
        return base_prompt
    return "\n\n".join(parts)

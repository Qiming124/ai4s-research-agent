# =============================================================================
# L4 结构化记忆注入：将定理/假设写入 system prompt。
#
# 职责：
#     1. format_structured_context() 格式化条目列表
#     2. build_structured_augmented_prompt() 合并工作区 + L4 记忆
#     3. 按 session 与 project 配置截断长度
#
# 架构位置：
#     - 被调用：server/agents/base.py、subagent.py
#     - 调用：memory/structured/store.py、theory_workspace.py
#
# 阅读提示：
#     - 新人先看 build_structured_augmented_prompt
#
# Debug：
#     - prompt 无 L4 内容 → ENABLE_STRUCTURED_MEMORY 或 session 无条目
# =============================================================================

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
    project_id = "default"
    if session_id:
        try:
            from server.memory.projects import get_project_store

            project_id = get_project_store().get_project_for_session(session_id)
        except Exception:
            project_id = "default"

    if agent_name in ("theory", "review"):
        workspace_ctx = format_workspace_context(cfg, project_id=project_id)
        if workspace_ctx:
            parts.append(workspace_ctx)
    if agent_name == "review":
        from server.memory.theory_workspace import load_review_checklist
        checklist = load_review_checklist(cfg, project_id=project_id)
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

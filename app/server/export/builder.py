# 从结构化记忆构建导出内容。

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.config import get_settings
from server.memory.bibliography import get_bibliography_store
from server.memory.manager import get_memory_manager
from server.memory.structured.store import get_structured_memory_store

KIND_LABELS = {
    "theorem": "定理",
    "lemma": "引理",
    "hypothesis": "假设",
    "note": "笔记",
    "definition": "定义",
}


def collect_export_entries(
    *,
    session_id: str | None = None,
    include_global: bool = True,
    include_chat: bool = True,
    limit: int = 100,
) -> list[dict[str, Any]]:
    store = get_structured_memory_store()
    entries: list[dict[str, Any]] = []
    seen: set[int] = set()
    if session_id:
        for entry in store.list_entries(session_id=session_id, limit=limit):
            eid = entry.get("id")
            if eid is not None and eid not in seen:
                seen.add(eid)
                entries.append(entry)
    if include_global:
        for entry in store.list_entries(global_only=True, limit=limit):
            eid = entry.get("id")
            if eid is not None and eid not in seen:
                seen.add(eid)
                entries.append(entry)
    if not entries and include_chat and session_id:
        entries = _chat_messages_as_entries(session_id)
    return entries


def build_markdown_document(*, title: str, entries: list[dict[str, Any]]) -> str:
    """将导出条目渲染为 Markdown（DOCX/PDF 的统一中间格式）。"""
    lines = [f"# {title or '研究报告'}", ""]
    if not entries:
        lines.append("（暂无定理/引理条目）")
        return "\n".join(lines)

    for entry in entries:
        kind = entry.get("kind", "note")
        entry_title = entry.get("title", "") or "未命名"
        body = (entry.get("body", "") or "").strip()
        label = KIND_LABELS.get(kind, kind)
        lines.append(f"## {label}：{entry_title}")
        lines.append("")
        if body:
            lines.append(body)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def describe_export_sources(
    *,
    session_id: str | None = None,
    include_global: bool = True,
    include_chat: bool = True,
) -> dict[str, Any]:
    """导出预览：条目数与来源说明。"""
    store = get_structured_memory_store()
    session_count = 0
    global_count = 0
    if session_id:
        session_count = len(store.list_entries(session_id=session_id, limit=200))
    if include_global:
        global_count = len(store.list_entries(global_only=True, limit=200))
    structured_total = session_count + global_count
    chat_count = len(_chat_messages_as_entries(session_id)) if session_id else 0
    entries = collect_export_entries(
        session_id=session_id,
        include_global=include_global,
        include_chat=include_chat,
    )
    if structured_total > 0:
        source = "structured_memory"
        hint = "内容来自定理库（L4）：当前会话 + 全局引理/定理。"
    elif chat_count > 0:
        source = "chat_fallback"
        hint = "暂无定理库条目，已回退导出本会话 AI 回答。"
    else:
        source = "empty"
        hint = (
            "暂无可导出内容。请先用 Math/Theory 模式对话，"
            "让系统抽取「## 定理/引理」写入定理库，或至少完成一轮对话后再导出。"
        )
    return {
        "entry_count": len(entries),
        "session_structured_count": session_count,
        "global_structured_count": global_count,
        "chat_message_count": chat_count,
        "source": source,
        "hint": hint,
    }


def _chat_messages_as_entries(session_id: str) -> list[dict[str, Any]]:
    """将助手回答转为可导出的 note 条目。"""
    memory = get_memory_manager()
    messages = memory.get_full_history(session_id)
    entries: list[dict[str, Any]] = []
    idx = 0
    for msg in messages:
        if msg.role != "assistant":
            continue
        content = (msg.content or "").strip()
        if not content:
            continue
        idx += 1
        entries.append(
            {
                "id": None,
                "kind": "note",
                "title": f"研究记录 {idx}",
                "body": content,
                "metadata": {"source": "chat_export"},
            }
        )
    return entries


def build_latex_document(
    *,
    title: str,
    entries: list[dict[str, Any]],
    project_id: str = "default",
) -> tuple[str, Path, str | None]:
    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath,amsthm}",
        r"\usepackage[UTF8]{ctex}",
        r"\newtheorem{theorem}{定理}",
        r"\newtheorem{lemma}{引理}",
        f"\\title{{{_escape_latex(title)}}}",
        r"\begin{document}",
        r"\maketitle",
    ]
    for entry in entries:
        kind = entry.get("kind", "note")
        entry_title = entry.get("title", "")
        body = entry.get("body", "")
        env = "theorem" if kind == "theorem" else "lemma" if kind in ("lemma", "hypothesis") else "theorem"
        lines.append(f"\\begin{{{env}}}[{_escape_latex(entry_title)}]")
        lines.append(_escape_latex(body)[:4000])
        lines.append(f"\\end{{{env}}}")
        lines.append("")

    settings = get_settings()
    proofs_dir = Path(settings.theory_workspace_path) / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)

    bib_path: str | None = None
    bib = get_bibliography_store().export_bibtex(project_id=project_id)
    if bib.strip():
        bib_file = proofs_dir / "references.bib"
        bib_file.write_text(bib, encoding="utf-8")
        bib_path = str(bib_file)
        lines.append(r"\bibliographystyle{plain}")
        lines.append(r"\bibliography{references}")

    lines.append(r"\end{document}")
    latex = "\n".join(lines)
    export_file = proofs_dir / "export.tex"
    export_file.write_text(latex, encoding="utf-8")
    return latex, export_file, bib_path


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = text or ""
    for char, escaped in replacements.items():
        out = out.replace(char, escaped)
    return out

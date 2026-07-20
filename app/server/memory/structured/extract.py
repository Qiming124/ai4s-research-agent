# =============================================================================
# 从 Theory Agent 输出抽取引理/定理并写入 L4 记忆。
#
# 职责：
#     1. 正则解析 ## 引理/定理 章节
#     2. 调用 graph 模块检测矛盾、提取 depends_on 元数据
#     3. persist_theory_sections() 批量写入 StructuredMemoryStore
#
# 架构位置：
#     - 被调用：server/agents/subagent.py（theory 角色后处理）
#     - 调用：memory/structured/graph.py、store.py
#
# 阅读提示：
#     - 新人先看 _SECTION_PATTERN 与 persist_theory_sections
#
# Debug：
#     - 未抽取 → 标题格式不符 ## 引理 N 模板
#     - 重复条目 → 同 session 多次 persist 未去重
# =============================================================================

from __future__ import annotations

import re
from typing import Any

from server.memory.structured.graph import (
    detect_contradictions,
    extract_metadata_from_body,
    link_depends_on_from_metadata,
)

_SECTION_PATTERN = re.compile(
    r"^#{2,3}\s+"
    r"(引理|定理|推论|Lemma|Theorem|Corollary)"
    r"\s*[:：]?\s*"
    r"(\d+)?"
    r"([^\n]*)",
    re.MULTILINE | re.IGNORECASE,
)

_THEOREM_KIND_LABELS = frozenset({"引理", "定理", "推论", "lemma", "theorem", "corollary"})


def extract_structured_entries(content: str) -> list[dict[str, Any]]:
    """按 Markdown 标题规则抽取引理/定理/推论块。

    返回:
        [{"kind": "theorem"|"note", "title": str, "body": str, "metadata": dict}, ...]
    """
    if not content.strip():
        return []

    matches = list(_SECTION_PATTERN.finditer(content))
    if not matches:
        return []

    entries: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        kind_label = match.group(1)
        number = match.group(2) or str(i + 1)
        extra_title = (match.group(3) or "").strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        kind = "theorem" if kind_label.lower() in _THEOREM_KIND_LABELS else "note"
        title = f"{kind_label} {number}"
        if extra_title:
            title = f"{title}: {extra_title}"

        if body:
            metadata = extract_metadata_from_body(body)
            metadata["status"] = "draft"
            entries.append(
                {"kind": kind, "title": title, "body": body, "metadata": metadata}
            )

    return entries


def try_persist_structured_entries(
    content: str,
    session_id: str,
    store,
    verification_results: list[dict[str, Any]] | None = None,
    *,
    source: str = "theory_auto_extract",
) -> tuple[list[dict[str, Any]], list[str]]:
    """若内容含引理/定理标题则抽取并写入；无匹配时返回 ([], [])。"""
    extracted = extract_structured_entries(content)
    if not extracted:
        return [], []
    return persist_extracted_entries(
        content,
        session_id,
        store,
        verification_results=verification_results,
        source=source,
    )


def persist_extracted_entries(
    content: str,
    session_id: str,
    store,
    verification_results: list[dict[str, Any]] | None = None,
    *,
    source: str = "theory_auto_extract",
) -> tuple[list[dict[str, Any]], list[str]]:
    """抽取并写入 StructuredMemoryStore；返回 (saved, warnings)。"""
    extracted = extract_structured_entries(content)
    saved: list[dict[str, Any]] = []
    warnings: list[str] = []
    existing = store.list_entries(session_id=session_id, limit=100)

    any_passed = any(
        r.get("status") == "pass" for r in (verification_results or [])
    )

    for item in extracted:
        for w in detect_contradictions(item, existing):
            warnings.append(w)
        meta = {**(item.get("metadata") or {}), "source": source}
        if any_passed:
            meta["status"] = "symbolically_verified"
        if verification_results:
            meta["verification_ledger"] = verification_results
        entry = store.create_entry(
            session_id=session_id,
            kind=item["kind"],
            title=item["title"],
            body=item["body"],
            metadata=meta,
        )
        link_depends_on_from_metadata(store, entry, session_id)
        saved.append(entry)
        existing.append(entry)

    return saved, warnings

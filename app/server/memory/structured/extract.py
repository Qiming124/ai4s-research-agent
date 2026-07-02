# 从 Theory Agent 输出中抽取引理/定理并写入 L4 结构化记忆。

from __future__ import annotations

import re
from typing import Any

from server.memory.structured.graph import (
    detect_contradictions,
    extract_metadata_from_body,
    link_depends_on_from_metadata,
)

_SECTION_PATTERN = re.compile(
    r"^##\s+(引理|定理|推论)\s*(\d+)?\s*(.*)$",
    re.MULTILINE,
)


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

        kind = "theorem" if kind_label in ("引理", "定理", "推论") else "note"
        title = f"{kind_label} {number}"
        if extra_title:
            title = f"{title}: {extra_title}"

        if body:
            metadata = extract_metadata_from_body(body)
            metadata["status"] = "proved"
            entries.append(
                {"kind": kind, "title": title, "body": body, "metadata": metadata}
            )

    return entries


def persist_extracted_entries(
    content: str,
    session_id: str,
    store,
) -> tuple[list[dict[str, Any]], list[str]]:
    """抽取并写入 StructuredMemoryStore；返回 (saved, warnings)。"""
    extracted = extract_structured_entries(content)
    saved: list[dict[str, Any]] = []
    warnings: list[str] = []
    existing = store.list_entries(session_id=session_id, limit=100)

    for item in extracted:
        for w in detect_contradictions(item, existing):
            warnings.append(w)
        entry = store.create_entry(
            session_id=session_id,
            kind=item["kind"],
            title=item["title"],
            body=item["body"],
            metadata={**(item.get("metadata") or {}), "source": "theory_auto_extract"},
        )
        link_depends_on_from_metadata(store, entry, session_id)
        saved.append(entry)
        existing.append(entry)

    return saved, warnings

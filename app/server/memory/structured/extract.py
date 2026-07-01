# 从 Theory Agent 输出中抽取引理/定理并写入 L4 结构化记忆。

from __future__ import annotations

import re
from typing import Any

_SECTION_PATTERN = re.compile(
    r"^##\s+(引理|定理|推论)\s*(\d+)?\s*(.*)$",
    re.MULTILINE,
)


def extract_structured_entries(content: str) -> list[dict[str, Any]]:
    """按 Markdown 标题规则抽取引理/定理/推论块。

    返回:
        [{"kind": "theorem"|"note", "title": str, "body": str}, ...]
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
            entries.append({"kind": kind, "title": title, "body": body})

    return entries


def persist_extracted_entries(
    content: str,
    session_id: str,
    store,
) -> list[dict[str, Any]]:
    """抽取并写入 StructuredMemoryStore。"""
    extracted = extract_structured_entries(content)
    saved: list[dict[str, Any]] = []
    for item in extracted:
        entry = store.create_entry(
            session_id=session_id,
            kind=item["kind"],
            title=item["title"],
            body=item["body"],
            metadata={"source": "theory_auto_extract"},
        )
        saved.append(entry)
    return saved

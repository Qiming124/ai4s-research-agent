# L4 知识图谱：依赖边、矛盾检测、工作区同步。

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from server.config import Settings, get_settings
from server.memory.structured.store import StructuredMemoryStore, get_structured_memory_store
from server.memory.theory_workspace import get_theory_workspace_path

logger = logging.getLogger(__name__)

_DEPENDS_PATTERN = re.compile(
    r"\*\*依据\*\*[：:]\s*(.+)$",
    re.MULTILINE,
)
_ASSUMPTIONS_PATTERN = re.compile(
    r"\*\*假设\*\*[：:]\s*(.+)$",
    re.MULTILINE,
)
_LEMMA_REF_PATTERN = re.compile(r"引理\s*(\d+)|定理\s*(\d+)")


def extract_metadata_from_body(body: str) -> dict[str, Any]:
    """从定理/引理正文中抽取假设与依据引用。"""
    meta: dict[str, Any] = {}
    m = _ASSUMPTIONS_PATTERN.search(body)
    if m:
        parts = [p.strip() for p in re.split(r"[,，、]", m.group(1)) if p.strip()]
        meta["assumptions"] = parts
    dep_match = _DEPENDS_PATTERN.search(body)
    if dep_match:
        refs = _LEMMA_REF_PATTERN.findall(dep_match.group(1))
        dep_ids = []
        for a, b in refs:
            dep_ids.append(a or b)
        if dep_ids:
            meta["depends_on_refs"] = dep_ids
    return meta


def detect_contradictions(
    new_entry: dict[str, Any],
    existing_entries: list[dict[str, Any]],
) -> list[str]:
    """简单矛盾检测：新定理假设与已有假设/结论冲突时返回警告。"""
    warnings: list[str] = []
    new_meta = new_entry.get("metadata") or {}
    new_assumptions = set(new_meta.get("assumptions", []))
    new_body = (new_entry.get("body") or "").lower()

    for old in existing_entries:
        old_title = old.get("title", "")
        old_body = (old.get("body") or "").lower()
        if old.get("kind") == "hypothesis" and "不" in new_body and old_title.lower() in new_body:
            warnings.append(f"新条目可能与假设「{old_title}」矛盾")
        old_meta = old.get("metadata") or {}
        old_assumptions = set(old_meta.get("assumptions", []))
        if new_assumptions and old_assumptions and new_assumptions.isdisjoint(old_assumptions):
            if "全局极小" in new_body and "鞍点" in old_body:
                warnings.append(f"假设集合与「{old_title}」不一致，请核对")
    return warnings


def sync_workspace_to_l4(settings: Settings | None = None) -> int:
    """扫描 data/theory/lemmas/*.md 同步到 L4（session_id=NULL 全局条目）。"""
    cfg = settings or get_settings()
    root = get_theory_workspace_path(cfg) / "lemmas"
    if not root.is_dir():
        return 0
    store = get_structured_memory_store()
    synced = 0
    for path in sorted(root.glob("*.md")):
        if path.name == ".gitkeep":
            continue
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            continue
        title = path.stem.replace("_", " ")
        existing = store.list_entries(session_id=None, kind="theorem", limit=200)
        if any(e.get("title") == title for e in existing):
            continue
        store.create_entry(
            session_id=None,
            kind="theorem",
            title=title,
            body=body,
            metadata={"source": "workspace_sync", "path": str(path.relative_to(root.parent))},
        )
        synced += 1
    if synced:
        logger.info("已同步 %d 条引理到 L4 全局记忆", synced)
    return synced


def link_depends_on_from_metadata(
    store: StructuredMemoryStore,
    entry: dict[str, Any],
    session_id: str | None,
) -> None:
    """根据 metadata.depends_on_refs 尝试创建 depends_on 边。"""
    meta = entry.get("metadata") or {}
    refs = meta.get("depends_on_refs") or []
    if not refs or entry.get("id") is None:
        return
    candidates = store.list_entries(session_id=session_id, kind="theorem", limit=100)
    candidates.extend(store.list_entries(session_id=None, kind="theorem", limit=100))
    for ref in refs:
        for cand in candidates:
            title = cand.get("title", "")
            if ref in title or title.endswith(ref):
                try:
                    store.create_edge(
                        from_id=int(entry["id"]),
                        to_id=int(cand["id"]),
                        relation="depends_on",
                    )
                except Exception:
                    pass

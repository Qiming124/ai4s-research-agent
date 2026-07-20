# =============================================================================
# L4 知识图谱：依赖边、矛盾检测、工作区同步。
#
# 职责：
#     1. 从正文 **依据** / **假设** 行解析 depends_on 边
#     2. detect_contradictions() 启发式矛盾检测
#     3. sync_assumptions_to_workspace() 回写 assumptions.md
#
# 架构位置：
#     - 被调用：memory/structured/extract.py、api/theory.py（间接）
#     - 调用：memory/structured/store.py、theory_workspace.py
#
# 阅读提示：
#     - 新人先看 link_depends_on_from_metadata、detect_contradictions
#
# Debug：
#     - 边未创建 → 正文缺少 **依据**： 格式
#     - 假矛盾 → 正则误匹配引理编号
# =============================================================================

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
    r"\*\*(?:依赖)?假设\*\*[：:]\s*(.+)$",
    re.MULTILINE,
)
_LEMMA_REF_PATTERN = re.compile(r"引理\s*(\d+)|定理\s*(\d+)")
_ASSUMPTION_ID_RE = re.compile(r"\bA(\d+)\b", re.IGNORECASE)


def normalize_assumption_list(parts: list[str]) -> list[str]:
    """从「A1（…）」等片段中抽出规范假设编号，去重保序。"""
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        match = _ASSUMPTION_ID_RE.search(str(part))
        if not match:
            continue
        aid = f"A{match.group(1)}"
        if aid not in seen:
            seen.add(aid)
            out.append(aid)
    return out


def extract_metadata_from_body(body: str) -> dict[str, Any]:
    """从定理/引理正文中抽取假设与依据引用。"""
    meta: dict[str, Any] = {}
    m = _ASSUMPTIONS_PATTERN.search(body)
    if m:
        parts = [p.strip() for p in re.split(r"[,，、]", m.group(1)) if p.strip()]
        assumptions = normalize_assumption_list(parts)
        if assumptions:
            meta["assumptions"] = assumptions
        elif parts:
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


def sync_workspace_to_l4(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> int:
    """扫描课题工作区 lemmas/*.md 同步到 L4（session_id=NULL 全局条目）。"""
    cfg = settings or get_settings()
    root = get_theory_workspace_path(cfg, project_id=project_id or "default") / "lemmas"
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
    from_id = int(entry["id"])
    existing = {
        (e["from_id"], e["to_id"], e["relation"])
        for e in store.list_edges(session_id=session_id)
    }
    candidates = store.list_entries(session_id=session_id, kind="theorem", limit=100)
    candidates.extend(store.list_entries(global_only=True, kind="theorem", limit=100))
    for ref in refs:
        for cand in candidates:
            if cand.get("id") == from_id:
                continue
            title = cand.get("title", "")
            if ref in title or title.endswith(ref):
                to_id = int(cand["id"])
                key = (from_id, to_id, "depends_on")
                if key in existing:
                    continue
                try:
                    store.create_edge(
                        from_id=from_id,
                        to_id=to_id,
                        relation="depends_on",
                    )
                    existing.add(key)
                except Exception:
                    pass

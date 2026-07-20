# =============================================================================
# 假设 DAG：失效传播与依赖查询。
#
# 职责：
#     1. build_assumption_dag() 从 structured_memory 构建 A1–A6 节点图
#     2. propagate_assumption_failure() 模拟某假设失效的下游影响
#     3. normalize_assumption_id() 统一 assumption 编号格式
#
# 架构位置：
#     - 被调用：server/api/theory.py
#     - 调用：memory/structured/store.py
#
# 阅读提示：
#     - 新人先看 build_assumption_dag 与 propagate_assumption_failure
#
# Debug：
#     - DAG 缺节点 → metadata 无 assumption_id 或 kind 非 hypothesis
#     - 传播为空 → 无边 depends_on 连接
# =============================================================================

from __future__ import annotations

import re
from typing import Any

from server.memory.structured.store import StructuredMemoryStore


ASSUMPTION_IDS = ("A1", "A2", "A3", "A4", "A5", "A6")
_ASSUMPTION_ID_RE = re.compile(r"\bA(\d+)\b", re.IGNORECASE)


def normalize_assumption_id(raw: str | int | None) -> str | None:
    """将 A1 / assumption-A1 / 「A1（…）」等统一为 A1 形式。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    lower = text.lower()
    if lower.startswith("assumption-"):
        text = text[len("assumption-") :]
    match = _ASSUMPTION_ID_RE.search(text)
    if not match:
        return None
    return f"A{match.group(1)}"


def assumption_node_id(assumption_id: str) -> str:
    return f"assumption-{assumption_id}"


def build_assumption_dag(
    store: StructuredMemoryStore,
    *,
    session_id: str | None = None,
    include_global: bool = True,
) -> dict[str, Any]:
    """构建假设-定理 DAG 视图。"""
    from server.memory.structured.graph import extract_metadata_from_body

    entries: list[dict[str, Any]] = []
    if session_id:
        entries.extend(store.list_entries(session_id=session_id, limit=200))
    if include_global:
        entries.extend(store.list_entries(global_only=True, limit=200))
    if not session_id and not include_global:
        entries.extend(store.list_entries(limit=200))

    seen: set[int] = set()
    nodes: list[dict[str, Any]] = []
    for e in entries:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        meta = e.get("metadata") or {}
        raw_assumptions = list(meta.get("assumptions", []) or [])
        if not raw_assumptions and e.get("body"):
            raw_assumptions = list(
                (extract_metadata_from_body(e["body"]).get("assumptions") or [])
            )
        normalized = [
            aid
            for aid in (normalize_assumption_id(a) for a in raw_assumptions)
            if aid
        ]
        nodes.append(
            {
                "id": e["id"],
                "kind": e["kind"],
                "title": e["title"],
                "status": meta.get("status", "draft"),
                "assumptions": normalized,
            }
        )

    for aid in ASSUMPTION_IDS:
        nodes.append(
            {
                "id": assumption_node_id(aid),
                "kind": "assumption",
                "title": aid,
                "status": "active",
                "assumptions": [],
            }
        )

    edges = store.list_edges(session_id=session_id)
    dag_edges: list[dict[str, Any]] = []
    for edge in edges:
        dag_edges.append(
            {
                "from_id": edge["from_id"],
                "to_id": edge["to_id"],
                "relation": edge["relation"],
            }
        )

    seen_requires: set[tuple[Any, str]] = set()
    for node in nodes:
        if node["kind"] == "assumption":
            continue
        for assumption in node.get("assumptions", []):
            aid = normalize_assumption_id(assumption)
            if not aid:
                continue
            key = (node["id"], aid)
            if key in seen_requires:
                continue
            seen_requires.add(key)
            dag_edges.append(
                {
                    "from_id": node["id"],
                    "to_id": assumption_node_id(aid),
                    "relation": "requires",
                }
            )

    return {"nodes": nodes, "edges": dag_edges}


def propagate_assumption_failure(
    dag: dict[str, Any],
    failed_assumption: str,
) -> list[dict[str, Any]]:
    """若某假设失效，返回受影响的定理节点。"""
    aid = normalize_assumption_id(failed_assumption)
    if not aid:
        return []
    target = assumption_node_id(aid)
    affected: list[dict[str, Any]] = []
    node_by_id = {n["id"]: n for n in dag.get("nodes", [])}
    for edge in dag.get("edges", []):
        if edge.get("to_id") == target and edge.get("relation") == "requires":
            node = node_by_id.get(edge["from_id"])
            if node and node.get("kind") in ("theorem", "hypothesis", "conclusion"):
                affected.append(node)
    return affected

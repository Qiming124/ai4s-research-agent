# 假设 DAG：失效传播与依赖查询。

from __future__ import annotations

from typing import Any

from server.memory.structured.store import StructuredMemoryStore


ASSUMPTION_IDS = ("A1", "A2", "A3", "A4", "A5", "A6")


def build_assumption_dag(
    store: StructuredMemoryStore,
    *,
    session_id: str | None = None,
    include_global: bool = True,
) -> dict[str, Any]:
    """构建假设-定理 DAG 视图。"""
    entries: list[dict[str, Any]] = []
    if session_id:
        entries.extend(store.list_entries(session_id=session_id, limit=200))
    if include_global:
        entries.extend(store.list_entries(global_only=True, limit=200))

    seen: set[int] = set()
    nodes: list[dict[str, Any]] = []
    for e in entries:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        meta = e.get("metadata") or {}
        nodes.append(
            {
                "id": e["id"],
                "kind": e["kind"],
                "title": e["title"],
                "status": meta.get("status", "draft"),
                "assumptions": meta.get("assumptions", []),
            }
        )

    for aid in ASSUMPTION_IDS:
        nodes.append(
            {
                "id": f"assumption-{aid}",
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

    for node in nodes:
        if node["kind"] == "assumption":
            continue
        for assumption in node.get("assumptions", []):
            aid = str(assumption).strip().upper()
            if not aid.startswith("A"):
                continue
            dag_edges.append(
                {
                    "from_id": node["id"],
                    "to_id": f"assumption-{aid}",
                    "relation": "requires",
                }
            )

    return {"nodes": nodes, "edges": dag_edges}


def propagate_assumption_failure(
    dag: dict[str, Any],
    failed_assumption: str,
) -> list[dict[str, Any]]:
    """若某假设失效，返回受影响的定理节点。"""
    aid = failed_assumption.strip().upper()
    target = f"assumption-{aid}"
    affected: list[dict[str, Any]] = []
    node_by_id = {n["id"]: n for n in dag.get("nodes", [])}
    for edge in dag.get("edges", []):
        if edge.get("to_id") == target and edge.get("relation") == "requires":
            node = node_by_id.get(edge["from_id"])
            if node and node.get("kind") in ("theorem", "hypothesis", "conclusion"):
                affected.append(node)
    return affected

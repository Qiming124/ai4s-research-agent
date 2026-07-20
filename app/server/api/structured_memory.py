# =============================================================================
# L4 结构化科研记忆 HTTP API。
#
# 职责：
#     1. CRUD 定理/引理/假设/结论等结构化条目
#     2. 管理记忆图谱边（depends_on / contradicts）
#     3. 按 session_id / kind 过滤列表
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/structured/store.py
#
# 阅读提示：
#     - 新人先看 list_structured_memory 与 create_structured_memory
#     - 图谱见 get_memory_graph / create_memory_edge
#
# Debug：
#     - 条目未出现在 prompt → injection.py 未启用或 session 过滤
#     - 边创建失败 → 源/目标 entry_id 不存在
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from server.memory.structured.store import get_structured_memory_store
from shared.schemas import (
    MemoryEdge,
    MemoryEdgeCreateRequest,
    MemoryGraphResponse,
    StructuredMemoryCreateRequest,
    StructuredMemoryEntry,
    StructuredMemoryListResponse,
)

router = APIRouter(tags=["memory"])


@router.get(
    "/v1/memory/structured",
    response_model=StructuredMemoryListResponse,
    summary="结构化记忆列表",
)
async def list_structured_memory(
    session_id: str | None = Query(
        default=None,
        description="按会话过滤",
        examples=["sess_demo"],
    ),
    kind: str | None = Query(
        default=None,
        description="按类型过滤：theorem/hypothesis/conclusion/citation/note",
        examples=["theorem"],
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="返回条数上限",
        examples=[50],
    ),
) -> StructuredMemoryListResponse:
    """按会话/类型列出 L4 结构化记忆条目。"""
    store = get_structured_memory_store()
    entries = store.list_entries(session_id=session_id, kind=kind, limit=limit)
    return StructuredMemoryListResponse(
        entries=[StructuredMemoryEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get(
    "/v1/memory/structured/global",
    response_model=StructuredMemoryListResponse,
    summary="全局结构化记忆",
)
async def list_global_structured_memory(
    kind: str | None = Query(
        default=None,
        description="按类型过滤",
        examples=["theorem"],
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="返回条数上限",
        examples=[50],
    ),
) -> StructuredMemoryListResponse:
    """仅列出全局（非会话绑定）结构化记忆。"""
    store = get_structured_memory_store()
    entries = store.list_entries(global_only=True, kind=kind, limit=limit)
    return StructuredMemoryListResponse(
        entries=[StructuredMemoryEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get(
    "/v1/memory/structured/{entry_id}/versions",
    summary="记忆条目版本列表",
)
async def list_entry_versions(
    entry_id: int = Path(..., description="记忆条目 ID", examples=[1]),
) -> dict:
    """列出某条目的 L4 历史版本。"""
    from server.memory.projects import get_project_store

    store = get_project_store()
    versions = store.list_entry_versions(entry_id)
    return {"entry_id": entry_id, "versions": versions, "total": len(versions)}


@router.post(
    "/v1/memory/structured/{entry_id}/versions",
    summary="新建记忆条目版本",
)
async def create_entry_version(
    entry_id: int = Path(..., description="记忆条目 ID", examples=[1]),
) -> dict:
    """基于当前条目内容快照新建一个版本。"""
    from server.memory.projects import get_project_store

    memory = get_structured_memory_store()
    entries = memory.list_entries(limit=500)
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    meta = entry.get("metadata") or {}
    version = get_project_store().save_entry_version(
        entry_id,
        entry["title"],
        entry["body"],
        meta,
        status=str(meta.get("status", "draft")),
    )
    return version


@router.get(
    "/v1/memory/structured/graph",
    response_model=MemoryGraphResponse,
    summary="知识图谱",
)
async def get_memory_graph(
    session_id: str | None = Query(
        default=None,
        description="按会话过滤节点/边",
        examples=["sess_demo"],
    ),
) -> MemoryGraphResponse:
    """返回结构化记忆节点与关系边。"""
    store = get_structured_memory_store()
    graph = store.get_graph(session_id=session_id)
    return MemoryGraphResponse(
        nodes=[StructuredMemoryEntry.model_validate(n) for n in graph["nodes"]],
        edges=[MemoryEdge.model_validate(e) for e in graph["edges"]],
    )


@router.post(
    "/v1/memory/structured",
    response_model=StructuredMemoryEntry,
    summary="写入结构化记忆",
)
async def create_structured_memory(
    request: StructuredMemoryCreateRequest,
) -> StructuredMemoryEntry:
    """新建一条定理/假设/结论等结构化记忆。"""
    store = get_structured_memory_store()
    entry = store.create_entry(
        session_id=request.session_id,
        kind=request.kind,
        title=request.title,
        body=request.body,
        metadata=request.metadata,
    )
    return StructuredMemoryEntry.model_validate(entry)


@router.post(
    "/v1/memory/structured/{entry_id}/edges",
    response_model=MemoryEdge,
    summary="创建知识图谱边",
)
async def create_memory_edge(
    request: MemoryEdgeCreateRequest,
    entry_id: int = Path(..., description="起点条目 ID", examples=[1]),
) -> MemoryEdge:
    """从 entry_id 指向 to_id，创建 depends_on/contradicts/supports/cites 边。"""
    store = get_structured_memory_store()
    try:
        edge = store.create_edge(
            from_id=entry_id,
            to_id=request.to_id,
            relation=request.relation,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MemoryEdge.model_validate(edge)

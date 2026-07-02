# L4 结构化科研记忆 API。

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

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


@router.get("/v1/memory/structured", response_model=StructuredMemoryListResponse)
async def list_structured_memory(
    session_id: str | None = Query(default=None, description="按会话过滤"),
    kind: str | None = Query(default=None, description="按类型过滤"),
    limit: int = Query(default=50, ge=1, le=200),
) -> StructuredMemoryListResponse:
    store = get_structured_memory_store()
    entries = store.list_entries(session_id=session_id, kind=kind, limit=limit)
    return StructuredMemoryListResponse(
        entries=[StructuredMemoryEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get("/v1/memory/structured/global", response_model=StructuredMemoryListResponse)
async def list_global_structured_memory(
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> StructuredMemoryListResponse:
    store = get_structured_memory_store()
    entries = store.list_entries(global_only=True, kind=kind, limit=limit)
    return StructuredMemoryListResponse(
        entries=[StructuredMemoryEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get("/v1/memory/structured/graph", response_model=MemoryGraphResponse)
async def get_memory_graph(
    session_id: str | None = Query(default=None),
) -> MemoryGraphResponse:
    store = get_structured_memory_store()
    graph = store.get_graph(session_id=session_id)
    return MemoryGraphResponse(
        nodes=[StructuredMemoryEntry.model_validate(n) for n in graph["nodes"]],
        edges=[MemoryEdge.model_validate(e) for e in graph["edges"]],
    )


@router.post("/v1/memory/structured", response_model=StructuredMemoryEntry)
async def create_structured_memory(
    request: StructuredMemoryCreateRequest,
) -> StructuredMemoryEntry:
    store = get_structured_memory_store()
    entry = store.create_entry(
        session_id=request.session_id,
        kind=request.kind,
        title=request.title,
        body=request.body,
        metadata=request.metadata,
    )
    return StructuredMemoryEntry.model_validate(entry)


@router.post("/v1/memory/structured/{entry_id}/edges", response_model=MemoryEdge)
async def create_memory_edge(
    entry_id: int,
    request: MemoryEdgeCreateRequest,
) -> MemoryEdge:
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

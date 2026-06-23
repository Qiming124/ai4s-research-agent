# L4 结构化科研记忆 API。

from __future__ import annotations

from fastapi import APIRouter, Query

from server.memory.structured.store import get_structured_memory_store
from shared.schemas import (
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

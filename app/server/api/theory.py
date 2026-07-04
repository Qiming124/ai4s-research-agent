# 理论工作区 API。

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from server.config import get_settings
from server.memory.bibliography import get_bibliography_store
from server.memory.structured.dag import build_assumption_dag, propagate_assumption_failure
from server.memory.structured.store import get_structured_memory_store
from server.memory.theory_workspace import (
    get_theory_workspace_path,
    list_workspace_files,
    load_assumptions,
    load_symbols,
)
from shared.schemas import (
    AssumptionDagResponse,
    BibliographyListResponse,
    WorkspaceFileInfo,
    WorkspaceListResponse,
    WorkspaceWriteRequest,
)

router = APIRouter(tags=["theory"])


@router.get("/v1/theory/workspace", response_model=WorkspaceListResponse)
async def list_theory_workspace() -> WorkspaceListResponse:
    files = list_workspace_files()
    return WorkspaceListResponse(
        files=[WorkspaceFileInfo(path=f["path"], kind=f["kind"]) for f in files],
    )


@router.get("/v1/theory/assumption-matrix", response_class=PlainTextResponse)
async def get_assumption_matrix() -> str:
    root = get_theory_workspace_path()
    path = root / "assumption_matrix.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="assumption_matrix.md 不存在")
    return path.read_text(encoding="utf-8")


@router.get("/v1/theory/symbols", response_class=PlainTextResponse)
async def get_symbols() -> str:
    return load_symbols() or ""


@router.get("/v1/theory/assumptions", response_class=PlainTextResponse)
async def get_assumptions() -> str:
    return load_assumptions() or ""


@router.put("/v1/theory/workspace/{file_path:path}", response_class=PlainTextResponse)
async def write_workspace_file(file_path: str, request: WorkspaceWriteRequest) -> str:
    root = get_theory_workspace_path()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="路径越界")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(request.content, encoding="utf-8")
    return "ok"


@router.get("/v1/theory/assumption-dag", response_model=AssumptionDagResponse)
async def get_assumption_dag(session_id: str | None = None) -> AssumptionDagResponse:
    store = get_structured_memory_store()
    dag = build_assumption_dag(store, session_id=session_id)
    return AssumptionDagResponse(nodes=dag["nodes"], edges=dag["edges"])


@router.get("/v1/theory/assumption-dag/impact/{assumption_id}")
async def assumption_impact(assumption_id: str, session_id: str | None = None) -> dict:
    store = get_structured_memory_store()
    dag = build_assumption_dag(store, session_id=session_id)
    affected = propagate_assumption_failure(dag, assumption_id)
    return {"assumption": assumption_id, "affected": affected}


@router.get("/v1/bibliography", response_model=BibliographyListResponse)
async def list_bibliography(project_id: str = "default") -> BibliographyListResponse:
    bib = get_bibliography_store()
    entries = bib.list_entries(project_id=project_id)
    return BibliographyListResponse(entries=entries, total=len(entries))


@router.get("/v1/bibliography/export.bib", response_class=PlainTextResponse)
async def export_bibliography(project_id: str = "default") -> str:
    return get_bibliography_store().export_bibtex(project_id=project_id)


@router.get("/v1/theory/workspace/{file_path:path}", response_class=PlainTextResponse)
async def read_workspace_file(file_path: str) -> str:
    root = get_theory_workspace_path()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="路径越界")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return target.read_text(encoding="utf-8")

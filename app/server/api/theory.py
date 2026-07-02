# 理论工作区 API。

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from server.config import get_settings
from server.memory.theory_workspace import (
    get_theory_workspace_path,
    list_workspace_files,
    load_assumptions,
    load_symbols,
)
from shared.schemas import WorkspaceFileInfo, WorkspaceListResponse

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


@router.get("/v1/theory/workspace/{file_path:path}", response_class=PlainTextResponse)
async def read_workspace_file(file_path: str) -> str:
    root = get_theory_workspace_path()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="路径越界")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return target.read_text(encoding="utf-8")

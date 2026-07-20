# =============================================================================
# 理论工作区 HTTP API。
#
# 职责：
#     1. 列出/读取课题理论工作区文件（symbols.md、assumptions.md 等）
#     2. 查询参考文献库与 L4 结构化记忆
#     3. 构建假设 DAG 并模拟假设失效传播
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/theory_workspace.py、bibliography.py、structured/dag.py、
#             structured/store.py
#
# 阅读提示：
#     - 新人先看 list_workspace 与 get_workspace_file
#     - 假设 DAG 见 get_assumption_dag / propagate_assumption
#
# Debug：
#     - 工作区为空 → data/theory/{project_id}/ 目录未初始化
#     - DAG 节点缺失 → structured_memory 无 assumption 类型条目
# =============================================================================

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from server.memory.bibliography import get_bibliography_store
from server.memory.projects import get_project_store
from server.memory.structured.dag import build_assumption_dag, propagate_assumption_failure
from server.memory.structured.store import get_structured_memory_store
from server.memory.theory_workspace import (
    get_theory_workspace_path,
    list_workspace_files,
    load_assumptions,
    load_symbols,
    resolve_project_id,
)
from shared.schemas import (
    AssumptionDagResponse,
    BibliographyListResponse,
    WorkspaceFileInfo,
    WorkspaceListResponse,
    WorkspaceWriteRequest,
)

router = APIRouter(tags=["theory"])


def _resolve_pid(project_id: str | None, session_id: str | None) -> str:
    if project_id and project_id.strip():
        return resolve_project_id(project_id)
    if session_id:
        return get_project_store().get_project_for_session(session_id)
    return "default"


@router.get("/v1/theory/workspace", response_model=WorkspaceListResponse)
async def list_theory_workspace(
    project_id: str = Query("default"),
    session_id: str | None = None,
) -> WorkspaceListResponse:
    pid = _resolve_pid(project_id, session_id)
    get_project_store().seed_theory_workspace(pid)
    files = list_workspace_files(project_id=pid)
    return WorkspaceListResponse(
        files=[WorkspaceFileInfo(path=f["path"], kind=f["kind"]) for f in files],
    )


@router.get("/v1/theory/assumption-matrix", response_class=PlainTextResponse)
async def get_assumption_matrix(
    project_id: str = Query("default"),
    session_id: str | None = None,
) -> str:
    pid = _resolve_pid(project_id, session_id)
    root = get_theory_workspace_path(project_id=pid)
    for name in ("assumption_matrix.md", "assumption-matrix.md"):
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="assumption_matrix.md 不存在")


@router.get("/v1/theory/symbols", response_class=PlainTextResponse)
async def get_symbols(
    project_id: str = Query("default"),
    session_id: str | None = None,
) -> str:
    pid = _resolve_pid(project_id, session_id)
    return load_symbols(project_id=pid) or ""


@router.get("/v1/theory/assumptions", response_class=PlainTextResponse)
async def get_assumptions(
    project_id: str = Query("default"),
    session_id: str | None = None,
) -> str:
    pid = _resolve_pid(project_id, session_id)
    return load_assumptions(project_id=pid) or ""


@router.put("/v1/theory/workspace/{file_path:path}", response_class=PlainTextResponse)
async def write_workspace_file(
    file_path: str,
    request: WorkspaceWriteRequest,
    project_id: str = Query("default"),
) -> str:
    pid = resolve_project_id(project_id)
    root = get_theory_workspace_path(project_id=pid)
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
    from server.memory.structured.dag import normalize_assumption_id

    store = get_structured_memory_store()
    dag = build_assumption_dag(store, session_id=session_id)
    affected = propagate_assumption_failure(dag, assumption_id)
    normalized = normalize_assumption_id(assumption_id) or assumption_id
    return {"assumption": normalized, "affected": affected}


@router.get("/v1/bibliography", response_model=BibliographyListResponse)
async def list_bibliography(project_id: str = "default") -> BibliographyListResponse:
    bib = get_bibliography_store()
    entries = bib.list_entries(project_id=project_id)
    return BibliographyListResponse(entries=entries, total=len(entries))


@router.get("/v1/bibliography/export.bib", response_class=PlainTextResponse)
async def export_bibliography(project_id: str = "default") -> str:
    return get_bibliography_store().export_bibtex(project_id=project_id)


@router.get("/v1/theory/workspace/{file_path:path}", response_class=PlainTextResponse)
async def read_workspace_file(
    file_path: str,
    project_id: str = Query("default"),
) -> str:
    pid = resolve_project_id(project_id)
    root = get_theory_workspace_path(project_id=pid)
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="路径越界")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return target.read_text(encoding="utf-8")

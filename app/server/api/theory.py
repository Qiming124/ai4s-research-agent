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

from fastapi import APIRouter, HTTPException, Path as PathParam, Query
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


@router.get(
    "/v1/theory/workspace",
    response_model=WorkspaceListResponse,
    summary="理论工作区文件列表",
)
async def list_theory_workspace(
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
    session_id: str | None = Query(
        default=None,
        description="可选：由会话反查课题",
        examples=["sess_demo"],
    ),
) -> WorkspaceListResponse:
    """列出课题理论工作区文件；若目录未初始化会先 seed。"""
    pid = _resolve_pid(project_id, session_id)
    get_project_store().seed_theory_workspace(pid)
    files = list_workspace_files(project_id=pid)
    return WorkspaceListResponse(
        files=[WorkspaceFileInfo(path=f["path"], kind=f["kind"]) for f in files],
    )


@router.get(
    "/v1/theory/assumption-matrix",
    response_class=PlainTextResponse,
    summary="假设矩阵 Markdown",
)
async def get_assumption_matrix(
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
    session_id: str | None = Query(
        default=None,
        description="可选：由会话反查课题",
        examples=["sess_demo"],
    ),
) -> str:
    """读取 assumption_matrix.md（或 assumption-matrix.md）纯文本。"""
    pid = _resolve_pid(project_id, session_id)
    root = get_theory_workspace_path(project_id=pid)
    for name in ("assumption_matrix.md", "assumption-matrix.md"):
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="assumption_matrix.md 不存在")


@router.get(
    "/v1/theory/symbols",
    response_class=PlainTextResponse,
    summary="符号表 Markdown",
)
async def get_symbols(
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
    session_id: str | None = Query(
        default=None,
        description="可选：由会话反查课题",
        examples=["sess_demo"],
    ),
) -> str:
    """读取 symbols.md 内容；不存在则返回空字符串。"""
    pid = _resolve_pid(project_id, session_id)
    return load_symbols(project_id=pid) or ""


@router.get(
    "/v1/theory/assumptions",
    response_class=PlainTextResponse,
    summary="假设列表 Markdown",
)
async def get_assumptions(
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
    session_id: str | None = Query(
        default=None,
        description="可选：由会话反查课题",
        examples=["sess_demo"],
    ),
) -> str:
    """读取 assumptions.md 内容；不存在则返回空字符串。"""
    pid = _resolve_pid(project_id, session_id)
    return load_assumptions(project_id=pid) or ""


@router.put(
    "/v1/theory/workspace/{file_path:path}",
    response_class=PlainTextResponse,
    summary="写入工作区文件",
)
async def write_workspace_file(
    request: WorkspaceWriteRequest,
    file_path: str = PathParam(..., description="相对工作区路径", examples=["assumptions.md"]),
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
) -> str:
    """覆盖写入理论工作区文件；禁止路径越界。成功返回 ok。"""
    pid = resolve_project_id(project_id)
    root = get_theory_workspace_path(project_id=pid)
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="路径越界")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(request.content, encoding="utf-8")
    return "ok"


@router.get(
    "/v1/theory/assumption-dag",
    response_model=AssumptionDagResponse,
    summary="假设依赖 DAG",
)
async def get_assumption_dag(
    session_id: str | None = Query(
        default=None,
        description="按会话过滤结构化记忆；省略则全局",
        examples=["sess_demo"],
    ),
) -> AssumptionDagResponse:
    """由结构化记忆构建假设依赖图（nodes + edges）。"""
    store = get_structured_memory_store()
    dag = build_assumption_dag(store, session_id=session_id)
    return AssumptionDagResponse(nodes=dag["nodes"], edges=dag["edges"])


@router.get(
    "/v1/theory/assumption-dag/impact/{assumption_id}",
    summary="假设失效影响传播",
)
async def assumption_impact(
    assumption_id: str = PathParam(
        ...,
        description="假设节点 ID",
        examples=["A1"],
    ),
    session_id: str | None = Query(
        default=None,
        description="按会话过滤",
        examples=["sess_demo"],
    ),
) -> dict:
    """模拟某假设失效后，沿 DAG 传播受影响的节点列表。"""
    from server.memory.structured.dag import normalize_assumption_id

    store = get_structured_memory_store()
    dag = build_assumption_dag(store, session_id=session_id)
    affected = propagate_assumption_failure(dag, assumption_id)
    normalized = normalize_assumption_id(assumption_id) or assumption_id
    return {"assumption": normalized, "affected": affected}


@router.get(
    "/v1/bibliography",
    response_model=BibliographyListResponse,
    summary="书目列表",
)
async def list_bibliography(
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
) -> BibliographyListResponse:
    """列出课题书目条目。"""
    bib = get_bibliography_store()
    entries = bib.list_entries(project_id=project_id)
    return BibliographyListResponse(entries=entries, total=len(entries))


@router.get(
    "/v1/bibliography/export.bib",
    response_class=PlainTextResponse,
    summary="导出 BibTeX",
)
async def export_bibliography(
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
) -> str:
    """导出课题全部书目为 .bib 纯文本。"""
    return get_bibliography_store().export_bibtex(project_id=project_id)


@router.get(
    "/v1/theory/workspace/{file_path:path}",
    response_class=PlainTextResponse,
    summary="读取工作区文件",
)
async def read_workspace_file(
    file_path: str = PathParam(..., description="相对工作区路径", examples=["assumptions.md"]),
    project_id: str = Query("default", description="课题 ID", examples=["default"]),
) -> str:
    """读取理论工作区文件全文；禁止路径越界。"""
    pid = resolve_project_id(project_id)
    root = get_theory_workspace_path(project_id=pid)
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="路径越界")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return target.read_text(encoding="utf-8")

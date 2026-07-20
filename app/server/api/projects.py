# =============================================================================
# 课题（Project）HTTP API。
#
# 职责：
#     1. CRUD 课题元数据、成员、任务与会话绑定
#     2. purge=true 时级联删除会话、Campaign 与工作区目录
#     3. 解析 project_id 别名（default / UUID / 名称）
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/projects.py、campaigns.py、session.py
#
# 阅读提示：
#     - 新人先看 list_projects / create_project / delete_project
#     - 级联删除逻辑在 delete_project 端点
#
# Debug：
#     - 404 课题不存在 → resolve_project_id 未匹配
#     - 删除失败 → 需 ?purge=true；default 课题不可删
#     - 会话未关联课题 → link_session 或创建时指定 project_id
# =============================================================================

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from server.config import get_settings
from server.memory.campaigns import get_campaign_store
from server.memory.projects import get_project_store
from server.memory.session import get_session_store
from shared.schemas import (
    ProjectCreateRequest,
    ProjectInfo,
    ProjectListResponse,
    ProjectMemberInfo,
    ProjectTaskCreateRequest,
    ProjectTaskInfo,
    ProjectTasksResponse,
    ProjectSessionInfo,
    ProjectSessionsResponse,
    ProjectUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.get("/v1/projects", response_model=ProjectListResponse)
async def list_projects() -> ProjectListResponse:
    store = get_project_store()
    projects = [ProjectInfo(**p) for p in store.list_projects()]
    return ProjectListResponse(projects=projects, total=len(projects))


@router.get("/v1/projects/{project_id}", response_model=ProjectInfo)
async def get_project(project_id: str) -> ProjectInfo:
    store = get_project_store()
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="课题不存在")
    return ProjectInfo(**project)


@router.post("/v1/projects", response_model=ProjectInfo)
async def create_project(request: ProjectCreateRequest) -> ProjectInfo:
    store = get_project_store()
    project = store.create_project(
        name=request.name,
        description=request.description,
        created_by=request.created_by,
    )
    store.ensure_workspace(project["id"])
    store.seed_theory_workspace(project["id"])
    return ProjectInfo(**project)


@router.patch("/v1/projects/{project_id}", response_model=ProjectInfo)
async def update_project(project_id: str, request: ProjectUpdateRequest) -> ProjectInfo:
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    project = store.update_project(
        project_id,
        name=request.name,
        description=request.description,
    )
    if not project:
        raise HTTPException(status_code=404, detail="课题不存在")
    return ProjectInfo(**project)


@router.delete("/v1/projects/{project_id}")
async def delete_project(
    project_id: str,
    purge: bool = Query(
        default=False,
        description="必须为 true：整包删除课题、关联会话、Campaign 与工作区文件",
    ),
) -> dict:
    """
    整包删除课题（需 ?purge=true）。

    - 默认课题 `default` 不可删
    - 级联：关联会话（含 RAG 会话引用）→ Campaign → 课题 RAG 文档 → DB 行 → data/projects/{id}
    """
    if project_id == "default":
        raise HTTPException(status_code=400, detail="默认课题不可删除")
    if not purge:
        raise HTTPException(
            status_code=400,
            detail="请使用 ?purge=true 确认整包删除课题及其会话与文件",
        )

    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")

    session_ids = [s["session_id"] for s in store.list_sessions(project_id)]
    session_store = get_session_store()
    settings = get_settings()
    deleted_sessions: list[str] = []
    for sid in session_ids:
        try:
            if session_store.delete_session(sid):
                deleted_sessions.append(sid)
            try:
                from server.memory.rag.session_refs import SessionRagRefStore
                from server.memory.rag.store import get_rag_store

                SessionRagRefStore(settings.session_db_path).clear_session(sid)
                get_rag_store().clear_session_documents(sid)
            except Exception:
                logger.exception("清除会话 RAG 失败 session_id=%s", sid)
        except Exception:
            logger.exception("删除会话失败 session_id=%s", sid)

    try:
        from server.memory.rag.store import get_rag_store

        get_rag_store().clear_project_documents(project_id)
    except Exception:
        logger.exception("清除课题 RAG 文档失败 project_id=%s", project_id)

    campaigns_deleted = 0
    try:
        campaigns_deleted = get_campaign_store().delete_campaigns_for_project(project_id)
    except Exception:
        logger.exception("删除 Campaign 失败 project_id=%s", project_id)

    try:
        result = store.delete_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="课题不存在")

    workspace = Path(result["workspace_root"])
    if workspace.exists():
        try:
            shutil.rmtree(workspace)
        except OSError:
            logger.exception("删除课题工作区失败 path=%s", workspace)

    return {
        "status": "deleted",
        "project_id": project_id,
        "name": result.get("name", ""),
        "deleted_sessions": deleted_sessions,
        "deleted_session_count": len(deleted_sessions),
        "deleted_campaigns": campaigns_deleted,
    }


@router.get("/v1/projects/{project_id}/members")
async def list_project_members(project_id: str) -> list[ProjectMemberInfo]:
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    return [ProjectMemberInfo(**m) for m in store.list_members(project_id)]


@router.get("/v1/projects/{project_id}/tasks", response_model=ProjectTasksResponse)
async def list_project_tasks(project_id: str) -> ProjectTasksResponse:
    store = get_project_store()
    resolved = store.resolve_project_id(project_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="课题不存在")
    tasks = [ProjectTaskInfo(**t) for t in store.list_tasks(resolved)]
    return ProjectTasksResponse(tasks=tasks, total=len(tasks))


@router.post("/v1/projects/{project_id}/tasks", response_model=ProjectTaskInfo)
async def create_project_task(
    project_id: str,
    request: ProjectTaskCreateRequest,
) -> ProjectTaskInfo:
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    task = store.create_task(
        project_id,
        request.title,
        description=request.description,
        assignee_role=request.assignee_role,
        related_entry_id=request.related_entry_id,
    )
    return ProjectTaskInfo(**task)


@router.patch("/v1/projects/{project_id}/tasks/{task_id}", response_model=ProjectTaskInfo)
async def update_project_task(
    project_id: str,
    task_id: int,
    status: str = Query(..., description="todo|in_progress|blocked|done"),
) -> ProjectTaskInfo:
    store = get_project_store()
    resolved = store.resolve_project_id(project_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="课题不存在")
    task = store.update_task_status(task_id, status)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ProjectTaskInfo(**task)


@router.get("/v1/projects/{project_id}/sessions", response_model=ProjectSessionsResponse)
async def list_project_sessions(project_id: str) -> ProjectSessionsResponse:
    store = get_project_store()
    resolved = store.resolve_project_id(project_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="课题不存在")
    sessions = [ProjectSessionInfo(**s) for s in store.list_sessions(resolved)]
    return ProjectSessionsResponse(sessions=sessions, total=len(sessions))


@router.post("/v1/projects/{project_id}/sessions/{session_id}")
async def link_session_to_project(project_id: str, session_id: str) -> dict:
    store = get_project_store()
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="课题不存在")
    store.link_session(project_id, session_id)
    store.append_audit(project_id, "link_session", payload={"session_id": session_id})
    return {"status": "ok", "project_id": project_id, "session_id": session_id}

# 课题 API。

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from server.memory.projects import get_project_store
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
)

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
    return ProjectInfo(**project)


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

# =============================================================================
# 实验运行与日志 HTTP API（按课题隔离 + CRUD）。
# =============================================================================

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Path as PathParam, Query

from server.experiments import log_store
from server.experiments.runner import run_config_async
from shared.schemas import (
    ExperimentRunInfo,
    ExperimentRunRequest,
    ExperimentRunUpdateRequest,
    ExperimentRunsResponse,
)

router = APIRouter(tags=["experiments"])


@router.post("/v1/experiments/runs", summary="触发实验运行")
async def create_experiment_run(request: ExperimentRunRequest) -> dict:
    """按 config_path 异步执行实验，返回 run 结果摘要。"""
    try:
        return await run_config_async(request.config_path, session_id=request.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/v1/experiments/runs",
    response_model=ExperimentRunsResponse,
    summary="实验运行列表（按课题）",
)
async def list_experiment_runs(
    project_id: str = Query(default="default", description="课题 ID（必填隔离键）"),
    session_id: str | None = Query(default=None, description="可选：按会话过滤"),
) -> ExperimentRunsResponse:
    """列出指定课题的实验记录（不含其他课题）。"""
    runs = log_store.list_runs(project_id, session_id=session_id)
    return ExperimentRunsResponse(runs=runs, total=len(runs))


@router.get("/v1/experiments/runs/{run_id}", summary="实验运行详情")
async def get_experiment_run(
    run_id: str = PathParam(..., description="运行 ID", examples=["run_20260720_001"]),
    project_id: str = Query(default="default", description="课题 ID"),
) -> dict[str, Any]:
    """读取单次实验运行的完整 JSON 日志（须属于该课题）。"""
    try:
        data = log_store.get_run(project_id, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    data.pop("_path", None)
    return data


@router.patch("/v1/experiments/runs/{run_id}", summary="更新实验记录字段")
async def update_experiment_run(
    request: ExperimentRunUpdateRequest,
    run_id: str = PathParam(..., description="运行 ID"),
    project_id: str = Query(..., description="课题 ID"),
) -> dict[str, Any]:
    """仅允许更新 name / summary / metrics / status。"""
    if (
        request.name is None
        and request.summary is None
        and request.metrics is None
        and request.status is None
    ):
        raise HTTPException(status_code=400, detail="未提供可更新字段")
    try:
        return log_store.update_run(
            project_id,
            run_id,
            name=request.name,
            summary=request.summary,
            metrics=request.metrics,
            status=request.status,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/v1/experiments/runs/{run_id}", summary="删除实验记录")
async def delete_experiment_run(
    run_id: str = PathParam(..., description="运行 ID"),
    project_id: str = Query(..., description="课题 ID"),
) -> dict[str, str]:
    """删除指定课题下的一条实验记录。"""
    try:
        ok = log_store.delete_run(project_id, run_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return {"status": "deleted", "run_id": run_id, "project_id": project_id}

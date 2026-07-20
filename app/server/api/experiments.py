# =============================================================================
# 实验运行与日志 HTTP API。
#
# 职责：
#     1. 接收 ExperimentRunRequest 并异步执行 yaml 配置实验
#     2. 列出 data/experiments/ 下的历史运行日志
#     3. 返回标准化 run_id、状态与 metrics 摘要
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/experiments/runner.py（run_config_async）
#
# 阅读提示：
#     - 新人先看 run_experiment 与 list_experiment_runs
#
# Debug：
#     - 运行失败 → experiments_path 下 yaml 不存在或 verification_executor 报错
#     - MCP 超时 → 勿在 FastAPI 循环内用 run_config 同步包装
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Path as PathParam

from server.config import get_settings
from server.experiments.runner import run_config_async
from shared.schemas import (
    ExperimentRunInfo,
    ExperimentRunRequest,
    ExperimentRunsResponse,
)

router = APIRouter(tags=["experiments"])


def _experiments_root() -> Path:
    return Path(get_settings().experiments_path)


def _list_runs() -> list[ExperimentRunInfo]:
    logs_dir = _experiments_root() / "logs"
    if not logs_dir.is_dir():
        return []
    runs: list[ExperimentRunInfo] = []
    for path in sorted(logs_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        runs.append(
            ExperimentRunInfo(
                run_id=data.get("run_id", path.stem),
                name=data.get("name", path.stem),
                config_path=data.get("config_path", ""),
                status=data.get("status", "completed"),
                log_path=str(path.relative_to(_experiments_root())),
                created_at=data.get("created_at"),
                summary=data.get("summary", {}),
                metrics=data.get("metrics", {}),
            )
        )
    return runs


@router.post("/v1/experiments/runs", summary="触发实验运行")
async def create_experiment_run(request: ExperimentRunRequest) -> dict:
    """按 config_path 异步执行实验，返回 run 结果摘要。"""
    try:
        # 在主事件循环 await，复用已连接的 MCP，避免嵌套 loop 报错/死锁
        return await run_config_async(request.config_path, session_id=request.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/v1/experiments/runs",
    response_model=ExperimentRunsResponse,
    summary="实验运行列表",
)
async def list_experiment_runs() -> ExperimentRunsResponse:
    """列出 experiments/logs 下历史运行记录。"""
    runs = _list_runs()
    return ExperimentRunsResponse(runs=runs, total=len(runs))


@router.get("/v1/experiments/runs/{run_id}", summary="实验运行详情")
async def get_experiment_run(
    run_id: str = PathParam(..., description="运行 ID", examples=["run_20260720_001"]),
) -> dict:
    """读取单次实验运行的完整 JSON 日志。"""
    logs_dir = _experiments_root() / "logs"
    path = logs_dir / f"{run_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return json.loads(path.read_text(encoding="utf-8"))

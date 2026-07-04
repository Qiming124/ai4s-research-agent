# 实验运行与日志 API。

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from server.config import get_settings
from server.experiments.runner import run_config
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


@router.post("/v1/experiments/runs")
async def create_experiment_run(request: ExperimentRunRequest) -> dict:
    try:
        return run_config(request.config_path, session_id=request.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/v1/experiments/runs", response_model=ExperimentRunsResponse)
async def list_experiment_runs() -> ExperimentRunsResponse:
    runs = _list_runs()
    return ExperimentRunsResponse(runs=runs, total=len(runs))


@router.get("/v1/experiments/runs/{run_id}")
async def get_experiment_run(run_id: str) -> dict:
    logs_dir = _experiments_root() / "logs"
    path = logs_dir / f"{run_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return json.loads(path.read_text(encoding="utf-8"))

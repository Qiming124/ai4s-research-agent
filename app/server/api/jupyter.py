# Jupyter 实验结果桥接 API。

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from server.config import get_settings
from shared.schemas import NotebookResultUploadRequest, NotebookResultUploadResponse

router = APIRouter(tags=["jupyter"])


@router.post("/v1/jupyter/upload-result", response_model=NotebookResultUploadResponse)
async def upload_notebook_result(
    request: NotebookResultUploadRequest,
) -> NotebookResultUploadResponse:
    settings = get_settings()
    root = Path(settings.experiments_path) / "notebooks" / "results"
    root.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())[:8]
    record = {
        "run_id": run_id,
        "name": request.name,
        "project_id": request.project_id,
        "session_id": request.session_id,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": request.summary,
        "metrics": request.metrics,
    }
    path = root / f"{run_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    logs_dir = Path(settings.experiments_path) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"nb_{run_id}.json"
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    return NotebookResultUploadResponse(
        run_id=run_id,
        log_path=str(log_path),
        status="indexed",
    )


@router.get("/v1/jupyter/template")
async def get_notebook_template(name: str = "loss_landscape") -> dict:
    templates = {
        "loss_landscape": {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": "# Loss Landscape 实验\n上传结果 JSON 至 POST /v1/jupyter/upload-result",
                },
                {
                    "cell_type": "code",
                    "source": (
                        "import json\n"
                        "import numpy as np\n"
                        "x = np.linspace(-2, 2, 50)\n"
                        "y = np.linspace(-2, 2, 50)\n"
                        "Z = x[:,None]**2 + y[None,:]**2\n"
                        "result = {'metrics': {'min_loss': float(Z.min())}}\n"
                        "print(json.dumps(result))"
                    ),
                },
            ],
        },
    }
    if name not in templates:
        raise HTTPException(status_code=404, detail="模板不存在")
    return templates[name]

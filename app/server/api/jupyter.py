# =============================================================================
# Jupyter / 实验数据回传 HTTP API。
#
# 支持：
#     - POST /v1/jupyter/upload-result  JSON body（summary + metrics）
#     - POST /v1/jupyter/upload-file    多格式文件：.json / .csv / .tsv / .xlsx
# =============================================================================

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from server.config import get_settings
from server.experiments.data_import import parse_experiment_file
from shared.schemas import NotebookResultUploadRequest, NotebookResultUploadResponse

router = APIRouter(tags=["jupyter"])
logger = logging.getLogger(__name__)


def _persist_experiment_record(
    *,
    name: str,
    project_id: str,
    session_id: str | None,
    summary: dict[str, Any],
    metrics: dict[str, Any],
    source: str = "jupyter_upload",
) -> NotebookResultUploadResponse:
    settings = get_settings()
    root = Path(settings.experiments_path) / "notebooks" / "results"
    root.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())[:8]
    record = {
        "run_id": run_id,
        "name": name,
        "project_id": project_id,
        "session_id": session_id,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "metrics": metrics,
        "source_format": source,
    }
    path = root / f"{run_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    logs_dir = Path(settings.experiments_path) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"nb_{run_id}.json"
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        from server.artifacts.store import get_artifact_store

        if settings.enable_artifact_store:
            get_artifact_store().save(
                "DataPacket",
                {
                    "project_id": project_id or "default",
                    "session_id": session_id,
                    "source": "jupyter_upload" if source in ("json", "jupyter_upload") else "manual",
                    "metrics": metrics or {},
                    "summary": {**(summary or {}), "import_format": source},
                    "log_path": str(log_path),
                    "raw_ref": run_id,
                    "title": name or f"nb_{run_id}",
                },
            )
    except Exception:
        logger.exception("DataPacket 旁路写入失败（不影响上传）")

    return NotebookResultUploadResponse(
        run_id=run_id,
        log_path=str(log_path),
        status="indexed",
    )


@router.post(
    "/v1/jupyter/upload-result",
    response_model=NotebookResultUploadResponse,
    summary="回传 Notebook 实验结果（JSON）",
)
async def upload_notebook_result(
    request: NotebookResultUploadRequest,
) -> NotebookResultUploadResponse:
    """将 Notebook 结果 JSON 写入 experiments 目录，并生成 run_id。"""
    return _persist_experiment_record(
        name=request.name,
        project_id=request.project_id or "default",
        session_id=request.session_id,
        summary=request.summary or {},
        metrics=request.metrics or {},
        source="json",
    )


@router.post(
    "/v1/jupyter/upload-file",
    response_model=NotebookResultUploadResponse,
    summary="上传实验数据文件（JSON/CSV/TSV/Excel）",
)
async def upload_experiment_file(
    file: UploadFile = File(..., description="实验数据文件：.json / .csv / .tsv / .xlsx"),
    name: str | None = Form(default=None, description="结果名称，默认用文件名"),
    project_id: str = Form(default="default", description="课题 ID"),
    session_id: str | None = Form(default=None, description="关联会话"),
) -> NotebookResultUploadResponse:
    """解析多格式表格/JSON，写入实验日志与 DataPacket。"""
    filename = file.filename or "upload.bin"
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大（上限 20MB）")
    try:
        parsed = parse_experiment_file(filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("解析实验文件失败")
        raise HTTPException(status_code=400, detail=f"解析失败: {exc}") from exc

    stem = Path(filename).stem
    result_name = (name or "").strip() or stem or "file_result"
    summary = dict(parsed.summary)
    if parsed.preview_rows and "preview" not in summary:
        summary["preview"] = parsed.preview_rows
    summary["source_filename"] = filename

    return _persist_experiment_record(
        name=result_name,
        project_id=project_id or "default",
        session_id=session_id,
        summary=summary,
        metrics=parsed.metrics,
        source=parsed.format,
    )

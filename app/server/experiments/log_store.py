# =============================================================================
# 实验运行日志存储：按课题隔离 + CRUD。
#
# 新写入：data/projects/{project_id}/experiments/logs/{run_id}.json
# 兼容读取：全局 data/experiments/logs/*.json（仅当记录内 project_id 匹配）
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.paths import DATA_ROOT
from server.config import get_settings
from shared.schemas import ExperimentRunInfo

logger = logging.getLogger(__name__)

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_experiments_root(project_id: str) -> Path:
    pid = (project_id or "default").strip() or "default"
    return DATA_ROOT / "projects" / pid / "experiments"


def project_logs_dir(project_id: str) -> Path:
    return project_experiments_root(project_id) / "logs"


def global_logs_dir() -> Path:
    return Path(get_settings().experiments_path) / "logs"


def _validate_run_id(run_id: str) -> str:
    rid = (run_id or "").strip()
    if not _SAFE_RUN_ID.match(rid):
        raise ValueError("非法 run_id")
    return rid


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _to_info(data: dict[str, Any], path: Path, *, project_id: str) -> ExperimentRunInfo:
    stem = path.stem
    # nb_xxx.json → run_id 优先用文件内字段，否则 stem
    run_id = str(data.get("run_id") or stem)
    if stem.startswith("nb_") and not data.get("run_id"):
        run_id = stem
    log_path = str(path)
    try:
        log_path = str(path.relative_to(DATA_ROOT))
    except ValueError:
        pass
    return ExperimentRunInfo(
        run_id=run_id,
        name=str(data.get("name") or run_id),
        config_path=str(data.get("config_path") or ""),
        status=str(data.get("status") or "completed"),
        log_path=log_path,
        created_at=data.get("created_at"),
        summary=data.get("summary") if isinstance(data.get("summary"), dict) else {},
        metrics=data.get("metrics") if isinstance(data.get("metrics"), dict) else {},
        project_id=str(data.get("project_id") or project_id),
        session_id=data.get("session_id"),
    )


def _iter_candidate_files(project_id: str) -> list[tuple[Path, str]]:
    """返回 (path, source_project_id_hint)。"""
    pid = (project_id or "default").strip() or "default"
    out: list[tuple[Path, str]] = []
    proj_dir = project_logs_dir(pid)
    if proj_dir.is_dir():
        for path in proj_dir.glob("*.json"):
            out.append((path, pid))
    gdir = global_logs_dir()
    if gdir.is_dir():
        for path in gdir.glob("*.json"):
            out.append((path, pid))
    return out


def list_runs(
    project_id: str,
    *,
    session_id: str | None = None,
) -> list[ExperimentRunInfo]:
    """列出某课题的实验记录（含兼容全局目录中带同 project_id 的旧文件）。"""
    pid = (project_id or "default").strip() or "default"
    seen: set[str] = set()
    runs: list[ExperimentRunInfo] = []
    for path, hint_pid in _iter_candidate_files(pid):
        data = _read_json(path)
        if not data:
            continue
        file_pid = str(data.get("project_id") or "").strip()
        # 课题目录内的文件默认归属该课题；全局目录必须显式匹配 project_id
        under_project = project_logs_dir(pid) in path.parents or path.parent == project_logs_dir(pid)
        if under_project:
            effective_pid = file_pid or hint_pid
        else:
            if file_pid != pid:
                continue
            effective_pid = file_pid
        if session_id and str(data.get("session_id") or "") != session_id:
            continue
        info = _to_info(data, path, project_id=effective_pid)
        if info.run_id in seen:
            continue
        seen.add(info.run_id)
        runs.append(info)
    runs.sort(key=lambda r: r.created_at or "", reverse=True)
    return runs


def resolve_run_file(project_id: str, run_id: str) -> Path | None:
    """定位记录文件：优先课题目录，再全局（匹配 project_id）。"""
    rid = _validate_run_id(run_id)
    pid = (project_id or "default").strip() or "default"
    candidates = [
        project_logs_dir(pid) / f"{rid}.json",
        project_logs_dir(pid) / f"nb_{rid}.json",
        global_logs_dir() / f"{rid}.json",
        global_logs_dir() / f"nb_{rid}.json",
    ]
    # 也扫目录内 run_id 字段匹配
    for path in candidates:
        if path.is_file():
            data = _read_json(path)
            if not data:
                continue
            under_project = path.parent == project_logs_dir(pid)
            file_pid = str(data.get("project_id") or "").strip()
            if under_project or file_pid == pid:
                return path
    for path, _ in _iter_candidate_files(pid):
        data = _read_json(path)
        if not data:
            continue
        under_project = path.parent == project_logs_dir(pid)
        file_pid = str(data.get("project_id") or "").strip()
        if not under_project and file_pid != pid:
            continue
        if str(data.get("run_id") or path.stem) == rid or path.stem in (rid, f"nb_{rid}"):
            return path
    return None


def get_run(project_id: str, run_id: str) -> dict[str, Any]:
    path = resolve_run_file(project_id, run_id)
    if not path:
        raise FileNotFoundError("运行记录不存在")
    data = _read_json(path)
    if not data:
        raise FileNotFoundError("运行记录损坏")
    data.setdefault("project_id", project_id)
    data["_path"] = str(path)
    return data


def save_run(record: dict[str, Any]) -> dict[str, Any]:
    """写入课题目录；返回落盘后的记录。"""
    pid = str(record.get("project_id") or "default").strip() or "default"
    rid = _validate_run_id(str(record.get("run_id") or ""))
    record = dict(record)
    record["project_id"] = pid
    record.setdefault("created_at", _utcnow())
    record.setdefault("updated_at", record["created_at"])
    dest_dir = project_logs_dir(pid)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{rid}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["log_path"] = str(path.relative_to(DATA_ROOT))
    return record


def update_run(
    project_id: str,
    run_id: str,
    *,
    name: str | None = None,
    summary: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    path = resolve_run_file(project_id, run_id)
    if not path:
        raise FileNotFoundError("运行记录不存在")
    data = _read_json(path)
    if not data:
        raise FileNotFoundError("运行记录损坏")
    file_pid = str(data.get("project_id") or "").strip()
    under_project = path.parent == project_logs_dir(project_id)
    if not under_project and file_pid and file_pid != project_id:
        raise PermissionError("记录不属于当前课题")
    if name is not None:
        data["name"] = name
    if summary is not None:
        data["summary"] = summary
    if metrics is not None:
        data["metrics"] = metrics
    if status is not None:
        data["status"] = status
    data["project_id"] = project_id or data.get("project_id") or "default"
    data["updated_at"] = _utcnow()
    # 若仍在全局目录，迁移到课题目录再写
    dest = project_logs_dir(project_id) / f"{_validate_run_id(str(data.get('run_id') or run_id))}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if path.resolve() != dest.resolve():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("迁移后删除旧日志失败 path=%s", path)
    return data


def delete_run(project_id: str, run_id: str) -> bool:
    path = resolve_run_file(project_id, run_id)
    if not path:
        return False
    data = _read_json(path) or {}
    file_pid = str(data.get("project_id") or "").strip()
    under_project = path.parent == project_logs_dir(project_id)
    if not under_project and file_pid and file_pid != project_id:
        raise PermissionError("记录不属于当前课题")
    path.unlink(missing_ok=True)
    # 清理可能的 notebooks/results 副本
    nb = Path(get_settings().experiments_path) / "notebooks" / "results" / f"{run_id}.json"
    if nb.is_file():
        try:
            nb_data = _read_json(nb) or {}
            if str(nb_data.get("project_id") or "") in ("", project_id):
                nb.unlink(missing_ok=True)
        except OSError:
            pass
    return True


def purge_project_experiments(project_id: str) -> None:
    """删除课题实验目录，并清理全局 logs 中带该 project_id 的文件。"""
    root = project_experiments_root(project_id)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    gdir = global_logs_dir()
    if not gdir.is_dir():
        return
    for path in gdir.glob("*.json"):
        data = _read_json(path)
        if data and str(data.get("project_id") or "") == project_id:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("清理全局实验日志失败 path=%s", path)

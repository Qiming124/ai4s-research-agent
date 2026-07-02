# 实验运行器：读取 yaml 配置、调用数值验证、写标准化日志。

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import get_settings


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        # 最小 yaml 解析回退
        data: dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip()
        return data
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_config(config_path: str | Path) -> dict[str, Any]:
    """执行实验配置并写入 logs/。"""
    settings = get_settings()
    root = Path(settings.experiments_path)
    cfg_path = Path(config_path)
    if not cfg_path.is_absolute():
        cfg_path = root / "configs" / cfg_path.name
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置不存在: {cfg_path}")

    config = _load_yaml(cfg_path)
    run_id = str(uuid.uuid4())[:8]
    name = str(config.get("name", cfg_path.stem))

    # 简化数值实验：对二次损失做 Hessian 采样示意
    summary: dict[str, Any] = {"name": name, "config": config}
    try:
        import numpy as np

        dim = 2
        rng = np.random.default_rng(int(config.get("seeds", [0])[0]) if config.get("seeds") else 0)
        point = rng.standard_normal(dim).tolist()
        summary["sample_point"] = point
        summary["note"] = "placeholder numerical summary; use numerical MCP for full runs"
    except ImportError:
        summary["note"] = "numpy not available"

    record = {
        "run_id": run_id,
        "name": name,
        "config_path": str(cfg_path.relative_to(root)) if cfg_path.is_relative_to(root) else str(cfg_path),
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }

    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{run_id}.json"
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["log_path"] = str(log_path)
    return record

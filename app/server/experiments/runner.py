# 实验运行器：读取 yaml 配置、调用验证执行器、写标准化日志。

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from server.config import get_settings
from server.experiments.verification_executor import (
    execute_claim_verification,
    run_verification_from_config,
)
from server.memory.claim_parser import parse_verifiable_claim


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
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


def run_config(config_path: str | Path, *, session_id: str | None = None) -> dict[str, Any]:
    """执行实验配置：优先 verifiable claim，其次 network 实验。"""
    settings = get_settings()
    root = Path(settings.experiments_path)
    cfg_path = Path(config_path)
    if not cfg_path.is_absolute():
        cfg_path = root / "configs" / cfg_path.name
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置不存在: {cfg_path}")

    config = _load_yaml(cfg_path)
    config["name"] = config.get("name", cfg_path.stem)

    if config.get("network") or config.get("tier_hint") == "experiment":
        from server.experiments.torch_runner import run_torch_experiment

        result = run_torch_experiment(config)
        result["config_path"] = str(
            cfg_path.relative_to(root) if cfg_path.is_relative_to(root) else str(cfg_path)
        )
        return result

    if config.get("verifiable") or config.get("expression") or config.get("claim"):
        return run_verification_from_config(
            config,
            config_path=str(
                cfg_path.relative_to(root) if cfg_path.is_relative_to(root) else str(cfg_path)
            ),
        )

    content = cfg_path.read_text(encoding="utf-8")
    claim = parse_verifiable_claim(content)
    if claim:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                execute_claim_verification(claim, session_id=session_id)
            )
        finally:
            loop.close()

    return run_verification_from_config(
        {
            "name": cfg_path.stem,
            "expression": config.get("expression", "x0**2 + x1**2"),
            "point": config.get("point", "0,0"),
            "expected": config.get("expected", {}),
        },
        config_path=str(cfg_path),
    )

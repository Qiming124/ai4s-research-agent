# 实验运行器：读取 yaml 配置、调用验证执行器、写标准化日志。

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.config import get_settings
from server.experiments.async_utils import run_coro_sync
from server.experiments.verification_executor import (
    execute_claim_verification,
    run_verification_from_config,
    run_verification_from_config_async,
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


def _resolve_config_path(config_path: str | Path) -> tuple[Path, Path]:
    settings = get_settings()
    root = Path(settings.experiments_path)
    cfg_path = Path(config_path)
    if not cfg_path.is_absolute():
        cfg_path = root / "configs" / cfg_path.name
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置不存在: {cfg_path}")
    return root, cfg_path


async def run_config_async(
    config_path: str | Path,
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """异步执行实验配置（FastAPI / Campaign 主循环请 await 本函数）。"""
    root, cfg_path = _resolve_config_path(config_path)
    config = _load_yaml(cfg_path)
    config["name"] = config.get("name", cfg_path.stem)
    rel = str(
        cfg_path.relative_to(root) if cfg_path.is_relative_to(root) else str(cfg_path)
    )

    if config.get("network") or config.get("tier_hint") == "experiment":
        from server.experiments.torch_runner import run_torch_experiment

        result = run_torch_experiment(config)
        result["config_path"] = rel
        if result.get("status") == "skipped":
            result["overall_passed"] = None
        return result

    if config.get("verifiable") or config.get("expression") or config.get("claim"):
        return await run_verification_from_config_async(
            config,
            config_path=rel,
            session_id=session_id,
        )

    content = cfg_path.read_text(encoding="utf-8")
    claim = parse_verifiable_claim(content)
    if claim:
        return await execute_claim_verification(claim, session_id=session_id)

    return await run_verification_from_config_async(
        {
            "name": cfg_path.stem,
            "expression": config.get("expression", "x0**2 + x1**2"),
            "point": config.get("point", "0,0"),
            "expected": config.get("expected", {}),
        },
        config_path=str(cfg_path),
        session_id=session_id,
    )


def run_config(config_path: str | Path, *, session_id: str | None = None) -> dict[str, Any]:
    """同步执行实验配置（仅 CLI / 无事件循环）。"""
    return run_coro_sync(run_config_async(config_path, session_id=session_id))

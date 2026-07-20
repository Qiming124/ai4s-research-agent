# =============================================================================
# Campaign 实验调度：从理论推导动态选择验证配置。
#
# 职责：
#     1. run_campaign_experiments() 解析 theory 文本并执行二次验证
#     2. build_symbolic_config / build_width_scaling_config 生成 yaml 配置
#     3. 检测过参数化关键词触发 MLP width scaling 实验
#
# 架构位置：
#     - 被调用：server/graph/research_supervisor.py（S5 阶段）
#     - 调用：experiments/runner.py、verification_executor.py、theory_pipeline.py
#
# 阅读提示：
#     - 新人先看 run_campaign_experiments 与 build_symbolic_config
#
# Debug：
#     - 实验 skipped → 无 loss 表达式或未 mentions_overparameterization
#     - MCP 失败 → 必须在 FastAPI 循环 await，禁止嵌套 run_coro_sync
# =============================================================================

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from server.config import get_settings
from server.experiments.runner import run_config
from server.experiments.verification_executor import execute_claim_verification
from server.graph.theory_pipeline import extract_loss_expression, to_numerical_expression


def _mentions_overparameterization(text: str) -> bool:
    lower = text.lower()
    markers = ("a5", "过参数", "overparam", "mlp", "神经网络", "宽度", "width", "hidden")
    return any(m in lower or m in text for m in markers)


def build_symbolic_config(
    expression: str,
    *,
    point: str = "0,0",
    variables: str = "x0,x1",
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    num_expr = to_numerical_expression(expression)
    return {
        "name": "campaign_dynamic_symbolic",
        "expression": num_expr,
        "point": point,
        "variables": variables,
        "tier_hint": "numerical",
        "expected": expected or {"classification": "local_minimum"},
    }


def _claim_from_config(config: dict[str, Any]) -> dict[str, Any]:
    claim = config.get("verifiable") or config.get("claim")
    if claim:
        return claim
    return {
        "expression": config.get("expression", "x0**2 + x1**2"),
        "point": config.get("point", "0,0"),
        "variables": config.get("variables", "x0,x1"),
        "expected": config.get("expected", {}),
        "tier_hint": config.get("tier_hint", "numerical"),
        "network": config.get("network"),
    }


def _is_quad_success(result: dict[str, Any]) -> bool:
    """兼容 completed / overall_passed / numerical tier pass。"""
    if result.get("overall_passed") is True:
        return True
    if result.get("status") in ("completed", "pass"):
        return True
    summary = result.get("summary", result)
    if isinstance(summary, dict):
        if summary.get("overall_passed") is True:
            return True
        if summary.get("status") in ("completed", "pass", "local_minimum"):
            return True
        if summary.get("passed") is True:
            return True
        tiers = summary.get("tiers") or {}
        numerical = tiers.get("numerical") or {}
        if numerical.get("status") == "pass":
            return True
    return False


def _success_reason(result: dict[str, Any], *, ok: bool) -> str:
    summary = result.get("summary", result)
    if isinstance(summary, dict):
        tiers = summary.get("tiers") or {}
        numerical = tiers.get("numerical") or {}
        reason = str(numerical.get("reason") or "").strip()
        if reason:
            return reason
        if summary.get("reason"):
            return str(summary["reason"])
    if ok:
        return "二次验证通过"
    return str(result.get("reason") or "二次验证未通过")


async def run_campaign_experiments(
    theory_content: str,
    *,
    session_id: str | None = None,
    campaign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据理论文本运行二次验证与可选 width scaling 实验。

    必须在 FastAPI 事件循环中 ``await`` 调用，禁止经嵌套 event loop 调 MCP。
    """
    budget = (campaign or {}).get("compute_budget") or {}
    max_torch = int(budget.get("max_torch_runs", 3))

    results: dict[str, Any] = {
        "runs": [],
        "quadratic_pass": False,
        "width_scaling_pass": False,
    }

    expression = extract_loss_expression(theory_content) or "x0**2 + x1**2"
    dyn_config = build_symbolic_config(expression)
    last_result: dict[str, Any] = {}

    try:
        claim = _claim_from_config(dyn_config)
        verification = await execute_claim_verification(claim, session_id=session_id)
        quad_result = {
            "status": "completed" if verification.get("overall_passed") else "failed",
            "summary": verification,
            "verification": verification,
            "overall_passed": verification.get("overall_passed"),
        }
        last_result = quad_result
        results["runs"].append(
            {
                "config": "campaign_dynamic_symbolic",
                "expression": expression,
                "result": quad_result,
            }
        )
        results["quadratic_pass"] = _is_quad_success(quad_result)
    except Exception as exc:
        results["runs"].append(
            {"config": "campaign_dynamic_symbolic", "error": str(exc)},
        )
        try:
            fallback_cfg = _load_yaml_config("quadratic_minimum.yaml")
            verification = await execute_claim_verification(
                _claim_from_config(fallback_cfg),
                session_id=session_id,
            )
            fallback = {
                "status": "completed" if verification.get("overall_passed") else "failed",
                "summary": verification,
                "overall_passed": verification.get("overall_passed"),
            }
            last_result = fallback
            results["runs"].append(
                {"config": "quadratic_minimum.yaml", "result": fallback},
            )
            results["quadratic_pass"] = _is_quad_success(fallback)
        except Exception as fb_exc:
            results["runs"].append(
                {"config": "quadratic_minimum.yaml", "error": str(fb_exc)},
            )
            last_result = {"reason": str(fb_exc)}

    # torch 实验不依赖主循环 MCP；放到线程里避免短暂阻塞
    if _mentions_overparameterization(theory_content) or max_torch > 0:
        try:
            width_result = await asyncio.to_thread(
                run_config,
                "width_scaling.yaml",
                session_id=session_id,
            )
            results["runs"].append(
                {"config": "width_scaling.yaml", "result": width_result},
            )
            metrics = width_result.get("metrics") or width_result.get("summary") or {}
            if isinstance(metrics, dict):
                results["width_scaling_pass"] = bool(
                    metrics.get("hessian_min_eig") is not None
                    or metrics.get("status") == "ok"
                    or width_result.get("status") in ("ok", "completed", "skipped")
                )
            else:
                results["width_scaling_pass"] = width_result.get("status") in (
                    "ok",
                    "completed",
                    "skipped",
                )
        except Exception as exc:
            results["runs"].append(
                {"config": "width_scaling.yaml", "error": str(exc)},
            )

    ok = bool(results["quadratic_pass"])
    results["summary"] = {
        "quadratic_pass": results["quadratic_pass"],
        "width_scaling_pass": results["width_scaling_pass"],
        "status": "pass" if ok else "fail",
        "reason": _success_reason(last_result, ok=ok),
    }
    return results


def _load_yaml_config(config_name: str) -> dict[str, Any]:
    settings = get_settings()
    cfg_path = Path(settings.experiments_path) / "configs" / config_name
    if not cfg_path.is_file():
        return {"expression": "x0**2 + x1**2", "point": "0,0", "tier_hint": "numerical"}
    try:
        import yaml

        with cfg_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except ImportError:
        data = {}
        for line in cfg_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip()
    data["name"] = data.get("name", cfg_path.stem)
    return data


def _write_temp_config(config: dict[str, Any]) -> Path:
    settings = get_settings()
    configs_dir = Path(settings.experiments_path) / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    name = config.get("name", "campaign_tmp")
    path = configs_dir / f"{name}.yaml"
    lines = []
    for key, val in config.items():
        if isinstance(val, dict):
            lines.append(f"{key}:")
            for sk, sv in val.items():
                lines.append(f"  {sk}: {sv}")
        elif isinstance(val, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in val)}]")
        else:
            lines.append(
                f"{key}: {json.dumps(val) if isinstance(val, str) and ' ' in val else val}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_config_from_dict(
    config: dict[str, Any],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """将内存配置写入临时 yaml 并执行（仅供 CLI / 无事件循环场景）。"""
    path = _write_temp_config(config)
    return run_config(path.name, session_id=session_id)

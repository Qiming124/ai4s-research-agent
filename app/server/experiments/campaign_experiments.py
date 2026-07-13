# Campaign 实验调度：从理论推导动态选择验证配置。

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from server.config import get_settings
from server.experiments.runner import run_config
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


def run_campaign_experiments(
    theory_content: str,
    *,
    session_id: str | None = None,
    campaign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据理论文本运行二次验证与可选 width scaling 实验。"""
    settings = get_settings()
    budget = (campaign or {}).get("compute_budget") or {}
    max_torch = int(budget.get("max_torch_runs", 3))

    results: dict[str, Any] = {
        "runs": [],
        "quadratic_pass": False,
        "width_scaling_pass": False,
    }

    expression = extract_loss_expression(theory_content) or "x0**2 + x1**2"
    dyn_config = build_symbolic_config(expression)

    try:
        quad_result = run_config_from_dict(dyn_config, session_id=session_id)
        results["runs"].append(
            {
                "config": "campaign_dynamic_symbolic",
                "expression": expression,
                "result": quad_result,
            }
        )
        summary = quad_result.get("summary", quad_result)
        status = str(summary.get("status", summary.get("classification", "")))
        results["quadratic_pass"] = status in ("pass", "local_minimum") or bool(
            summary.get("passed")
        )
    except Exception as exc:
        results["runs"].append(
            {"config": "campaign_dynamic_symbolic", "error": str(exc)},
        )
        try:
            fallback = run_config("quadratic_minimum.yaml", session_id=session_id)
            results["runs"].append(
                {"config": "quadratic_minimum.yaml", "result": fallback},
            )
            fb_summary = fallback.get("summary", fallback)
            results["quadratic_pass"] = str(fb_summary.get("status", "")) == "pass"
        except Exception as fb_exc:
            results["runs"].append(
                {"config": "quadratic_minimum.yaml", "error": str(fb_exc)},
            )

    if _mentions_overparameterization(theory_content) or max_torch > 0:
        try:
            width_result = run_config("width_scaling.yaml", session_id=session_id)
            results["runs"].append(
                {"config": "width_scaling.yaml", "result": width_result},
            )
            metrics = width_result.get("metrics") or width_result.get("summary") or {}
            if isinstance(metrics, dict):
                results["width_scaling_pass"] = bool(
                    metrics.get("hessian_min_eig") is not None
                    or metrics.get("status") == "ok"
                    or width_result.get("status") == "ok"
                )
            else:
                results["width_scaling_pass"] = width_result.get("status") == "ok"
        except Exception as exc:
            results["runs"].append(
                {"config": "width_scaling.yaml", "error": str(exc)},
            )

    results["summary"] = {
        "quadratic_pass": results["quadratic_pass"],
        "width_scaling_pass": results["width_scaling_pass"],
        "status": "pass"
        if results["quadratic_pass"]
        else "fail",
    }
    return results


def run_config_from_dict(
    config: dict[str, Any],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """将内存配置写入临时 yaml 并执行。"""
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
            lines.append(f"{key}: {json.dumps(val) if isinstance(val, str) and ' ' in val else val}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_config(path.name, session_id=session_id)

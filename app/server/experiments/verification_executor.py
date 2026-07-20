# =============================================================================
# 验证执行器：将 Claim 或 YAML 配置转为可执行数值验证。
#
# 职责：
#     1. execute_claim_verification() 调用 MCP numerical/sympy 并写验证账本
#     2. run_verification_from_config_async() 执行完整 yaml 实验流程
#     3. 本地多项式 eval 回退（MCP 不可用时）
#
# 架构位置：
#     - 被调用：server/api/verification.py、experiments/runner.py、
#               campaign_experiments.py、graph/theory_pipeline.py
#     - 调用：server/mcp/client.py、memory/verification.py、claim_parser.py
#
# 阅读提示：
#     - 新人先看 execute_claim_verification 与 run_verification_from_config_async
#
# Debug：
#     - persist 后查不到 → project_id 与 session 所属课题不一致
#     - MCP 超时 → get_mcp_client 未 connect
# =============================================================================

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import get_settings
from server.experiments.async_utils import run_coro_sync
from server.graph.theory_pipeline import to_numerical_expression
from server.memory.claim_parser import claim_from_content_or_expression, parse_verifiable_claim
from server.memory.verification import get_verification_ledger
from server.mcp.client import get_mcp_client


def _eval_polynomial_local(expression: str, point: list[float]) -> float:
    env: dict[str, Any] = {
        "x0": point[0] if point else 0.0,
        "x1": point[1] if len(point) > 1 else 0.0,
        "theta": point[0] if point else 0.0,
        "sin": __import__("math").sin,
        "cos": __import__("math").cos,
        "exp": __import__("math").exp,
        "sqrt": __import__("math").sqrt,
        "abs": abs,
    }
    return float(eval(expression.replace("^", "**"), {"__builtins__": {}}, env))  # noqa: S307


def _nonempty_reason(*parts: Any, fallback: str) -> str:
    for part in parts:
        text = str(part or "").strip()
        if text:
            return text
    return fallback


async def execute_claim_verification(
    claim: dict[str, Any],
    *,
    session_id: str | None = None,
    project_id: str = "default",
    entry_id: int | None = None,
    agent_name: str = "verification_executor",
    persist: bool = True,
) -> dict[str, Any]:
    """对结构化 Claim 执行 Tier1/2 验证；persist=True 时写入账本。"""
    mcp = await get_mcp_client()
    expression = claim.get("expression", "")
    point = claim.get("point", "0,0")
    variables = claim.get("variables", "x0,x1")
    expected = claim.get("expected") or {}
    tier_hint = claim.get("tier_hint", "numerical")
    results: dict[str, Any] = {"claim": claim, "tiers": {}}

    sympy_result: dict[str, Any] = {"status": "skipped", "reason": "tier_hint=numerical"}
    if tier_hint in ("symbolic", "auto"):
        try:
            sym_expr = expression.replace("x0", "theta").replace("x1", "theta2")
            grad_raw = await mcp.call_tool(
                "sympy__differentiate",
                {"expression": sym_expr, "variable": "theta"},
            )
            if not (grad_raw or "").strip():
                sympy_result = {
                    "status": "fail",
                    "reason": "empty MCP response",
                    "details": {},
                }
            else:
                grad_data = json.loads(grad_raw)
                if "error" in grad_data:
                    sympy_result = {
                        "status": "fail",
                        "reason": _nonempty_reason(
                            grad_data.get("error"),
                            fallback="SymPy 梯度验证失败",
                        ),
                        "details": grad_data,
                    }
                else:
                    sympy_result = {
                        "status": "pass",
                        "reason": "SymPy 梯度验证通过",
                        "details": grad_data,
                    }
        except Exception as exc:
            sympy_result = {
                "status": "fail",
                "reason": _nonempty_reason(exc, fallback="SymPy 验证异常"),
                "details": {},
            }
    results["tiers"]["symbolic"] = sympy_result

    ledger = get_verification_ledger()
    if persist and sympy_result.get("status") == "pass":
        ledger.append(
            project_id=project_id,
            session_id=session_id,
            entry_id=entry_id,
            claim_id=expression[:64],
            tier="symbolic",
            executor="sympy__differentiate",
            agent_name=agent_name,
            passed=True,
            result=sympy_result,
        )

    num_expr = to_numerical_expression(expression)
    num_result: dict[str, Any]
    try:
        raw = await mcp.call_tool(
            "numerical__critical_point_classify",
            {"expression": num_expr, "point": point, "variables": variables},
        )
        if not (raw or "").strip():
            num_result = {
                "status": "fail",
                "reason": "empty MCP response",
                "details": {},
            }
        else:
            data = json.loads(raw)
            if "error" in data:
                num_result = {
                    "status": "fail",
                    "reason": _nonempty_reason(
                        data.get("error"),
                        fallback="numerical tool returned error",
                    ),
                    "details": data,
                }
            else:
                classification = data.get("classification", "unknown")
                expected_cls = expected.get("classification")
                passed = True
                if expected_cls:
                    passed = classification == expected_cls
                elif classification in ("local_minimum", "saddle", "local_maximum"):
                    passed = True
                else:
                    passed = False
                num_result = {
                    "status": "pass" if passed else "fail",
                    "reason": f"分类={classification}",
                    "details": data,
                    "passed": passed,
                }
    except Exception as exc:
        num_result = {
            "status": "fail",
            "reason": _nonempty_reason(exc, fallback="numerical verification exception"),
            "details": {},
        }

    results["tiers"]["numerical"] = num_result
    if persist:
        ledger.append(
            project_id=project_id,
            session_id=session_id,
            entry_id=entry_id,
            claim_id=expression[:64],
            tier="numerical",
            executor="numerical__critical_point_classify",
            agent_name=agent_name,
            passed=num_result.get("status") == "pass",
            result=num_result,
        )

    if tier_hint == "experiment" or claim.get("network"):
        from server.experiments.torch_runner import run_torch_experiment

        exp_result = run_torch_experiment(claim)
        results["tiers"]["experiment"] = exp_result
        exp_status = exp_result.get("status")
        if persist:
            ledger.append(
                project_id=project_id,
                session_id=session_id,
                entry_id=entry_id,
                claim_id=expression[:64],
                tier="experiment",
                executor="torch_runner",
                agent_name=agent_name,
                # skipped 不计入失败
                passed=exp_status in ("completed", "skipped"),
                result=exp_result,
                artifacts=[exp_result.get("log_path", "")] if exp_result.get("log_path") else [],
            )

    active = [
        t for t in results["tiers"].values() if t.get("status") not in ("skipped", None)
    ]
    if not active:
        results["overall_passed"] = True
    else:
        results["overall_passed"] = all(
            t.get("status") in ("pass", "completed") for t in active
        )
    results["has_skips"] = any(
        t.get("status") == "skipped" for t in results["tiers"].values()
    )
    return results


def _claim_from_config(config: dict[str, Any]) -> dict[str, Any] | None:
    claim = config.get("verifiable") or config.get("claim")
    if claim:
        return claim
    if config.get("expression"):
        return {
            "expression": config["expression"],
            "point": config.get("point", "0,0"),
            "variables": config.get("variables", "x0,x1"),
            "expected": config.get("expected", {}),
            "tier_hint": config.get("tier_hint", "numerical"),
            "network": config.get("network"),
        }
    return None


async def run_verification_from_config_async(
    config: dict[str, Any],
    config_path: str = "",
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """异步执行 YAML/Claim 验证并写实验日志（供 FastAPI / S5 主循环 await）。"""
    settings = get_settings()
    run_id = str(uuid.uuid4())[:8]
    claim = _claim_from_config(config)
    if not claim:
        return {
            "run_id": run_id,
            "status": "failed",
            "reason": "配置缺少 verifiable/claim/expression",
        }

    result = await execute_claim_verification(
        claim,
        project_id=config.get("project_id", "default"),
        session_id=session_id,
    )

    tiers = result.get("tiers") or {}
    active = [t for t in tiers.values() if t.get("status") not in ("skipped", None)]
    if not active and tiers:
        status = "skipped"
    elif result.get("overall_passed"):
        status = "completed"
    else:
        status = "failed"

    record = {
        "run_id": run_id,
        "name": config.get("name", "verification_run"),
        "config_path": config_path,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": result,
        "verification": result,
    }

    logs_dir = Path(settings.experiments_path) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{run_id}.json"
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["log_path"] = str(log_path)
    return record


def run_verification_from_config(config: dict[str, Any], config_path: str = "") -> dict[str, Any]:
    """同步包装：仅用于 CLI / 无事件循环场景。"""
    return run_coro_sync(run_verification_from_config_async(config, config_path))


def run_verification_from_content(content: str, **kwargs: Any) -> dict[str, Any]:
    """从 Theory 输出文本执行验证。"""
    claim = parse_verifiable_claim(content)
    if not claim:
        from server.graph.theory_pipeline import extract_loss_expression

        expr = extract_loss_expression(content)
        claim = claim_from_content_or_expression(content, expr)
    if not claim:
        return {"status": "skipped", "reason": "无可验证 Claim"}
    return run_coro_sync(execute_claim_verification(claim, **kwargs))

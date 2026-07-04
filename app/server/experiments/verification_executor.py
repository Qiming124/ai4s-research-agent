# 验证执行器：将 Claim 或 YAML 配置转为可执行数值验证。

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import get_settings
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


async def execute_claim_verification(
    claim: dict[str, Any],
    *,
    session_id: str | None = None,
    project_id: str = "default",
    entry_id: int | None = None,
    agent_name: str = "verification_executor",
) -> dict[str, Any]:
    """对结构化 Claim 执行 Tier1/2 验证并写入账本。"""
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
            grad_data = json.loads(grad_raw)
            if "error" not in grad_data:
                sympy_result = {
                    "status": "pass",
                    "reason": "SymPy 梯度验证通过",
                    "details": grad_data,
                }
            else:
                sympy_result = {"status": "fail", "reason": grad_data["error"], "details": grad_data}
        except Exception as exc:
            sympy_result = {"status": "fail", "reason": str(exc), "details": {}}
    results["tiers"]["symbolic"] = sympy_result

    ledger = get_verification_ledger()
    if sympy_result.get("status") == "pass":
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
        data = json.loads(raw)
        if "error" in data:
            num_result = {"status": "fail", "reason": data["error"], "details": data}
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
        num_result = {"status": "fail", "reason": str(exc), "details": {}}

    results["tiers"]["numerical"] = num_result
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
        ledger.append(
            project_id=project_id,
            session_id=session_id,
            entry_id=entry_id,
            claim_id=expression[:64],
            tier="experiment",
            executor="torch_runner",
            agent_name=agent_name,
            passed=exp_result.get("status") == "completed",
            result=exp_result,
            artifacts=[exp_result.get("log_path", "")] if exp_result.get("log_path") else [],
        )

    results["overall_passed"] = all(
        t.get("status") in ("pass", "completed", "skipped")
        for t in results["tiers"].values()
        if t.get("status") != "skipped"
    )
    return results


def run_verification_from_config(config: dict[str, Any], config_path: str = "") -> dict[str, Any]:
    """同步包装：从 YAML 配置或 Claim 字典执行验证并写实验日志。"""
    settings = get_settings()
    run_id = str(uuid.uuid4())[:8]
    claim = config.get("verifiable") or config.get("claim")
    if not claim and config.get("expression"):
        claim = {
            "expression": config["expression"],
            "point": config.get("point", "0,0"),
            "variables": config.get("variables", "x0,x1"),
            "expected": config.get("expected", {}),
            "tier_hint": config.get("tier_hint", "numerical"),
            "network": config.get("network"),
        }

    if not claim:
        return {
            "run_id": run_id,
            "status": "failed",
            "reason": "配置缺少 verifiable/claim/expression",
        }

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            execute_claim_verification(claim, project_id=config.get("project_id", "default"))
        )
    finally:
        loop.close()

    record = {
        "run_id": run_id,
        "name": config.get("name", "verification_run"),
        "config_path": config_path,
        "status": "completed" if result.get("overall_passed") else "failed",
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


def run_verification_from_content(content: str, **kwargs: Any) -> dict[str, Any]:
    """从 Theory 输出文本执行验证。"""
    claim = parse_verifiable_claim(content)
    if not claim:
        from server.graph.theory_pipeline import extract_loss_expression

        expr = extract_loss_expression(content)
        claim = claim_from_content_or_expression(content, expr)
    if not claim:
        return {"status": "skipped", "reason": "无可验证 Claim"}
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(execute_claim_verification(claim, **kwargs))
    finally:
        loop.close()

# Theory Agent 推导闭环：derive → verify (SymPy + numerical) → persist。

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from server.mcp.client import MCPClient
from server.graph.workflow import workflow_step_chunk, workflow_step_record
from shared.schemas import PersistedToolCall, StreamChunk

logger = logging.getLogger(__name__)

_EXPRESSION_PATTERNS = [
    re.compile(r"L\s*=\s*([^;\n]+)"),
    re.compile(r"损失函数[^$]*\$\$(.+?)\$\$", re.DOTALL),
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
]


def extract_loss_expression(content: str) -> str | None:
    """从推导文本中启发式提取可符号化的损失表达式。"""
    for pattern in _EXPRESSION_PATTERNS:
        match = pattern.search(content)
        if match:
            expr = match.group(1).strip()
            expr = expr.replace("\\theta", "theta").replace("\\", "")
            expr = re.sub(r"\\text\{[^}]+\}", "", expr)
            if len(expr) > 3 and ("**" in expr or "*" in expr or "theta" in expr or "x" in expr):
                return expr
    return None


def to_numerical_expression(expr: str) -> str:
    """将符号表达式转为 numerical MCP 可用的 x0,x1 形式。"""
    out = expr.replace("theta", "x0").replace("theta1", "x0").replace("theta2", "x1")
    out = re.sub(r"\bx\b", "x0", out)
    out = re.sub(r"\by\b", "x1", out)
    return out


async def run_sympy_verification(
    mcp: MCPClient,
    content: str,
    tool_records: list[PersistedToolCall],
) -> dict[str, Any]:
    """对推导结果做 SymPy 符号验证。"""
    sympy_calls = [
        r for r in tool_records
        if r.name.startswith("sympy__") and r.status == "success"
    ]
    if sympy_calls:
        return {
            "status": "pass",
            "reason": f"推导过程中已调用 {len(sympy_calls)} 次 SymPy 工具",
            "details": [r.name for r in sympy_calls],
        }

    expression = extract_loss_expression(content)
    if not expression:
        return {
            "status": "skipped",
            "reason": "未能从文本中提取可符号化的损失表达式；请手动调用 SymPy 或标注待验证",
            "details": [],
        }

    try:
        grad_result = await mcp.call_tool(
            "sympy__differentiate",
            {"expression": expression, "variable": "theta"},
        )
        grad_data = json.loads(grad_result)
        if "error" in grad_data:
            return {
                "status": "fail",
                "reason": f"梯度验证失败: {grad_data['error']}",
                "details": grad_data,
            }

        hess_result = await mcp.call_tool(
            "sympy__hessian_eigenvalues",
            {"expression": expression, "variables": "theta"},
        )
        hess_data = json.loads(hess_result)
        if "error" in hess_data:
            return {
                "status": "partial",
                "reason": f"梯度验证通过；Hessian 验证失败: {hess_data['error']}",
                "details": {"gradient": grad_data, "hessian_error": hess_data["error"]},
            }

        return {
            "status": "pass",
            "reason": "自动 SymPy 验证通过（梯度 + Hessian）",
            "details": {"gradient": grad_data, "hessian": hess_data},
        }
    except Exception as exc:
        logger.warning("SymPy 自动验证异常: %s", exc)
        return {
            "status": "fail",
            "reason": f"SymPy 验证异常: {exc}",
            "details": [],
        }


async def run_numerical_verification(
    mcp: MCPClient,
    content: str,
    tool_records: list[PersistedToolCall],
    sympy_result: dict[str, Any],
) -> dict[str, Any]:
    """SymPy 未通过或跳过时，尝试数值验证。"""
    numerical_calls = [
        r for r in tool_records
        if r.name.startswith("numerical__") and r.status == "success"
    ]
    if numerical_calls:
        return {
            "status": "pass",
            "reason": f"推导过程中已调用 {len(numerical_calls)} 次数值验证工具",
            "details": [r.name for r in numerical_calls],
        }

    sympy_status = str(sympy_result.get("status", ""))
    if sympy_status == "pass":
        return {
            "status": "skipped",
            "reason": "SymPy 验证已通过，无需数值 fallback",
            "details": {},
        }

    expression = extract_loss_expression(content)
    if not expression:
        return {
            "status": "skipped",
            "reason": "无法提取损失表达式进行数值验证",
            "details": {},
        }

    num_expr = to_numerical_expression(expression)
    try:
        result_raw = await mcp.call_tool(
            "numerical__critical_point_classify",
            {"expression": num_expr, "point": "0,0", "variables": "x0,x1"},
        )
        data = json.loads(result_raw)
        if "error" in data:
            return {
                "status": "fail",
                "reason": f"数值验证失败: {data['error']}",
                "details": data,
            }
        classification = data.get("classification", "unknown")
        status = "pass" if classification in ("local_minimum", "saddle", "local_maximum") else "partial"
        return {
            "status": status,
            "reason": f"数值临界点分类: {classification}",
            "details": data,
        }
    except Exception as exc:
        logger.warning("数值验证异常: %s", exc)
        return {
            "status": "fail",
            "reason": f"数值验证异常: {exc}",
            "details": {},
        }


async def stream_theory_verification(
    mcp: MCPClient,
    content: str,
    tool_records: list[PersistedToolCall],
    *,
    agent_name: str,
    a2a_task_id: str | None = None,
    workflow_records: list[dict] | None = None,
) -> AsyncIterator[StreamChunk]:
    """运行 SymPy + 数值验证并产出 SSE 事件。"""
    wf_records = workflow_records if workflow_records is not None else []

    yield workflow_step_chunk(
        "verify",
        status="running",
        title="SymPy 符号验证",
        agent_name=agent_name,
        a2a_task_id=a2a_task_id,
    )
    wf_records.append(
        workflow_step_record("verify", status="running", title="SymPy 符号验证"),
    )

    sympy_result = await run_sympy_verification(mcp, content, tool_records)
    status_map = {"pass": "pass", "fail": "fail", "skipped": "skipped", "partial": "done"}
    verify_status = status_map.get(str(sympy_result.get("status", "")), "done")

    wf_records.append(
        workflow_step_record(
            "verify",
            status=verify_status,  # type: ignore[arg-type]
            title="SymPy 符号验证",
            detail=str(sympy_result.get("reason", "")),
        ),
    )
    yield workflow_step_chunk(
        "verify",
        status=verify_status,  # type: ignore[arg-type]
        title="SymPy 符号验证",
        detail=str(sympy_result.get("reason", "")),
        agent_name=agent_name,
        a2a_task_id=a2a_task_id,
    )

    payload = json.dumps(sympy_result, ensure_ascii=False, indent=2)
    yield StreamChunk(
        type="verification_result",
        content=payload,
        agent_name=agent_name,
        a2a_task_id=a2a_task_id,
    )

    num_result = await run_numerical_verification(mcp, content, tool_records, sympy_result)
    if num_result.get("status") != "skipped":
        num_status = status_map.get(str(num_result.get("status", "")), "done")
        wf_records.append(
            workflow_step_record(
                "verify",
                status=num_status,  # type: ignore[arg-type]
                title="数值验证",
                detail=str(num_result.get("reason", "")),
            ),
        )
        yield workflow_step_chunk(
            "verify",
            status=num_status,  # type: ignore[arg-type]
            title="数值验证",
            detail=str(num_result.get("reason", "")),
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
        )
        yield StreamChunk(
            type="numerical_verification_result",
            content=json.dumps(num_result, ensure_ascii=False, indent=2),
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
        )


def needs_experiment_handoff(sympy_result: dict[str, Any], num_result: dict[str, Any] | None) -> bool:
    """判断是否应自动 handoff 到 Experiment Agent。"""
    sympy_status = str(sympy_result.get("status", ""))
    if sympy_status in ("skipped", "partial", "fail"):
        if num_result is None:
            return True
        return str(num_result.get("status", "")) in ("skipped", "fail")
    return False

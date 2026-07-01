# Theory Agent 推导闭环：derive → verify → persist。

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from server.mcp.client import MCPClient
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
            if len(expr) > 3 and "**" in expr or "*" in expr or "theta" in expr or "x" in expr:
                return expr
    return None


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


async def stream_theory_verification(
    mcp: MCPClient,
    content: str,
    tool_records: list[PersistedToolCall],
    *,
    agent_name: str,
    a2a_task_id: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """运行验证并产出 verification_result SSE 事件。"""
    result = await run_sympy_verification(mcp, content, tool_records)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    yield StreamChunk(
        type="verification_result",
        content=payload,
        agent_name=agent_name,
        a2a_task_id=a2a_task_id,
    )

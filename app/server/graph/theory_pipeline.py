# =============================================================================
# Theory Agent 推导闭环：derive → verify → persist。
#
# 职责：
#     1. 从推导文本抽取 loss 表达式与可验证 Claim
#     2. 调用 SymPy / numerical MCP 做符号与数值验证
#     3. 写入验证账本并发出 workflow SSE 步骤
#     4. 判断是否需要 experiment Agent handoff
#
# 架构位置：
#     - 被调用：server/graph/research_pipeline.py、research_supervisor.py、
#               experiments/campaign_experiments.py、verification_executor.py
#     - 调用：server/mcp/client.py、memory/verification.py、graph/workflow.py
#
# 阅读提示：
#     - 新人先看 extract_loss_expression、run_sympy_verification、
#       run_numerical_verification
#
# Debug：
#     - SymPy 跳过 → 无 sympy__ 成功 tool call 或表达式无法 parse
#     - 数值验证失败 → to_numerical_expression 转换或 MCP numerical 未连接
# =============================================================================

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from server.memory.claim_parser import claim_from_content_or_expression, parse_verifiable_claim
from server.memory.verification import get_verification_ledger
from server.mcp.client import MCPClient
from server.graph.workflow import upsert_workflow_record, workflow_step_chunk, workflow_step_record
from shared.schemas import PersistedToolCall, StreamChunk

logger = logging.getLogger(__name__)

_EXPRESSION_PATTERNS = [
    re.compile(r"L\s*\(\s*[^)]+\)\s*=\s*([^\n;]+)"),
    re.compile(r"L\s*=\s*([^\n;]+)"),
    re.compile(r"损失函数[^$]*\$\$([^$]+?)\$\$", re.DOTALL),
    re.compile(r"\$\$([^$]+?)\$\$", re.DOTALL),
]

_LATEX_NOISE = re.compile(
    r"(\\begin|\\end|\\mathbb|\\quad|\\qquad|\\in\b|\\top|\\cdot|\\frac|\\\\)",
    re.I,
)


def parse_verifiable_claim_from_content(content: str) -> dict[str, Any] | None:
    """解析结构化 verifiable Claim 块。"""
    return parse_verifiable_claim(content)


def _looks_like_python_expr(expr: str) -> bool:
    """拒绝整段 LaTeX / 叙述句，只保留可数值求值的表达式。"""
    compact = expr.replace(" ", "")
    if len(compact) < 3 or len(compact) > 200:
        return False
    if _LATEX_NOISE.search(expr):
        return False
    # 去反斜杠后的 LaTeX 残留词
    if re.search(r"\b(mathbb|quad|qquad|dfrac|frac|cdot|times)\b", expr, re.I):
        return False
    # 方程左右两边（f(x)=...）通常不是纯表达式
    if "=" in expr and not expr.strip().startswith("="):
        if re.search(r"(?<![*=<>!])=(?!=)", expr):
            return False
    if not re.search(r"(theta|\bx\d*\b|\*\*|\^|\*)", expr, re.I):
        return False
    # 允许的字符大致对齐 numerical MCP
    cleaned = expr.replace("^", "**").replace("\\theta", "theta")
    cleaned = re.sub(r"\\", "", cleaned)
    return bool(re.match(r"^[\w\s+\-*/().,**]+$", cleaned.replace(" ", "")))


def _normalize_captured_expr(raw: str) -> str:
    """清洗捕获串：去 LaTeX 命令、去掉 ``L =`` 前缀、截断中文叙述。"""
    expr = raw.strip()
    expr = expr.replace("\\theta", "theta")
    expr = re.sub(r"\\text\{[^}]+\}", "", expr)
    expr = expr.replace("\\", "")
    # $$L = theta**2 + 1$$ → theta**2 + 1
    expr = re.sub(r"^[Ll]\s*\([^)]*\)\s*=\s*", "", expr)
    expr = re.sub(r"^[Ll]\s*=\s*", "", expr)
    # 截断中文/叙述
    expr = re.split(r"[\u4e00-\u9fff]", expr, maxsplit=1)[0]
    expr = expr.strip().rstrip(".,;，。；")
    return expr


def extract_loss_expression(content: str) -> str | None:
    """从推导文本中启发式提取可符号化的损失表达式。"""
    claim = parse_verifiable_claim(content)
    if claim and claim.get("expression"):
        return str(claim["expression"])
    for pattern in _EXPRESSION_PATTERNS:
        match = pattern.search(content)
        if match:
            expr = _normalize_captured_expr(match.group(1))
            if _looks_like_python_expr(expr):
                return expr
    return None


def to_numerical_expression(expr: str) -> str:
    """将符号表达式转为 numerical MCP 可用的 x0,x1 形式。"""
    # 必须先替换长标识，避免 theta1 → x01
    out = expr
    out = out.replace("theta2", "x1").replace("theta1", "x0").replace("theta0", "x0")
    out = out.replace("theta", "x0")
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

    claim = claim_from_content_or_expression(content, extract_loss_expression(content))
    expression = (claim or {}).get("expression") or extract_loss_expression(content)
    if not expression:
        return {
            "status": "skipped",
            "reason": "未能从文本中提取可符号化的损失表达式；请手动调用 SymPy 或标注待验证",
            "details": [],
        }

    point = (claim or {}).get("point", "0,0")
    try:
        sym_expr = expression.replace("x0", "theta").replace("x1", "theta2")
        grad_result = await mcp.call_tool(
            "sympy__differentiate",
            {"expression": sym_expr, "variable": "theta"},
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
            {"expression": sym_expr, "variables": "theta,theta2"},
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

    claim = claim_from_content_or_expression(content, extract_loss_expression(content))
    expression = (claim or {}).get("expression") or extract_loss_expression(content)
    if not expression:
        return {
            "status": "skipped",
            "reason": "无法提取损失表达式进行数值验证",
            "details": {},
        }

    point = (claim or {}).get("point", "0,0")
    variables = (claim or {}).get("variables", "x0,x1")
    expected = (claim or {}).get("expected") or {}
    num_expr = to_numerical_expression(expression)
    try:
        result_raw = await mcp.call_tool(
            "numerical__critical_point_classify",
            {"expression": num_expr, "point": point, "variables": variables},
        )
        data = json.loads(result_raw)
        if "error" in data:
            return {
                "status": "fail",
                "reason": f"数值验证失败: {data['error']}",
                "details": data,
            }
        classification = data.get("classification", "unknown")
        expected_cls = expected.get("classification")
        if expected_cls:
            status = "pass" if classification == expected_cls else "fail"
        else:
            status = "pass" if classification in ("local_minimum", "saddle", "local_maximum") else "partial"
        return {
            "status": status,
            "reason": f"数值临界点分类: {classification}",
            "details": data,
            "claim": claim,
        }
    except Exception as exc:
        logger.warning("数值验证异常: %s", exc)
        return {
            "status": "fail",
            "reason": f"数值验证异常: {exc}",
            "details": {},
        }


def _record_verification_ledger(
    *,
    session_id: str | None,
    tier: str,
    passed: bool,
    result: dict[str, Any],
    agent_name: str,
    entry_id: int | None = None,
) -> None:
    try:
        claim = result.get("claim") or {}
        get_verification_ledger().append(
            session_id=session_id,
            entry_id=entry_id,
            claim_id=str(claim.get("expression", result.get("reason", "")))[:64],
            tier=tier,
            executor=f"theory_pipeline:{tier}",
            agent_name=agent_name,
            passed=passed,
            result=result,
        )
    except Exception as exc:
        logger.warning("验证账本写入失败: %s", exc)


async def stream_theory_verification(
    mcp: MCPClient,
    content: str,
    tool_records: list[PersistedToolCall],
    *,
    agent_name: str,
    a2a_task_id: str | None = None,
    workflow_records: list[dict] | None = None,
    session_id: str | None = None,
    entry_id: int | None = None,
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
    upsert_workflow_record(
        wf_records,
        workflow_step_record("verify", status="running", title="SymPy 符号验证"),
    )

    sympy_result = await run_sympy_verification(mcp, content, tool_records)
    status_map = {"pass": "pass", "fail": "fail", "skipped": "skipped", "partial": "done"}
    verify_status = status_map.get(str(sympy_result.get("status", "")), "done")

    upsert_workflow_record(
        wf_records,
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

    claim = claim_from_content_or_expression(content, extract_loss_expression(content))
    if claim:
        sympy_result["claim"] = claim
    _record_verification_ledger(
        session_id=session_id,
        tier="symbolic",
        passed=str(sympy_result.get("status")) == "pass",
        result=sympy_result,
        agent_name=agent_name,
        entry_id=entry_id,
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
        upsert_workflow_record(
            wf_records,
            workflow_step_record(
                "verify",
                status=num_status,  # type: ignore[arg-type]
                title="数值验证",
                detail=str(num_result.get("reason", "")),
                tool_call_id="wf-verify-numerical",
            ),
        )
        yield workflow_step_chunk(
            "verify",
            status=num_status,  # type: ignore[arg-type]
            title="数值验证",
            detail=str(num_result.get("reason", "")),
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
            tool_call_id="wf-verify-numerical",
        )
        _record_verification_ledger(
            session_id=session_id,
            tier="numerical",
            passed=str(num_result.get("status")) == "pass",
            result=num_result,
            agent_name=agent_name,
            entry_id=entry_id,
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

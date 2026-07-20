# =============================================================================
# MCP Server：数值验证（梯度、Hessian 谱、loss landscape、SGD）。
#
# 职责：
#     1. eval_polynomial、hessian_spectrum、loss_landscape_slice 等工具
#     2. 基于 NumPy 本地计算，解析 point 字符串为坐标
#     3. 返回 JSON metrics 供 Theory / Experiment Agent 验证 Claim
#
# 架构位置：
#     - 被调用：MCP Client stdio 子进程、verification_executor.py
#     - 调用：numpy（可选）
#
# 阅读提示：
#     - 新人先看 eval_polynomial 与 hessian_min_eigenvalue
#
# Debug：
#     - NumPy 未安装 → pip install numpy
#     - 表达式 parse 失败 → 仅支持受限多项式/初等函数语法
# =============================================================================

from __future__ import annotations

import json
import math
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("numerical")

_EPS = 1e-5


def _import_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("NumPy 未安装。请执行: pip install numpy") from exc
    return np


def _parse_point(point: str, dim: int) -> list[float]:
    parts = [p.strip() for p in point.split(",") if p.strip()]
    if not parts:
        return [0.0] * dim
    vals = [float(p) for p in parts]
    while len(vals) < dim:
        vals.append(0.0)
    return vals[:dim]


def _eval_polynomial(expr: str, x: list[float]) -> float:
    """安全求值低维多项式表达式（x0,x1,... 或 theta）。"""
    np = _import_numpy()
    env: dict[str, Any] = {
        "x0": x[0] if x else 0.0,
        "x1": x[1] if len(x) > 1 else 0.0,
        "x2": x[2] if len(x) > 2 else 0.0,
        "theta": x[0] if x else 0.0,
        "pi": math.pi,
        "e": math.e,
        "sin": math.sin,
        "cos": math.cos,
        "exp": math.exp,
        "sqrt": math.sqrt,
        "abs": abs,
        "min": min,
        "max": max,
    }
    for i, xi in enumerate(x):
        env[f"x{i}"] = xi
    cleaned = expr.replace("^", "**")
    cleaned = re.sub(r"\\theta", "theta", cleaned)
    if not re.match(r"^[\w\s+\-*/().,**]+$", cleaned.replace(" ", "")):
        raise ValueError(f"表达式含不允许的字符: {expr}")
    return float(eval(cleaned, {"__builtins__": {}}, env))  # noqa: S307


def _loss_fn(expr: str, dim: int):
    def fn(x: list[float]) -> float:
        return _eval_polynomial(expr, x)

    return fn


@mcp.tool()
async def numerical_gradient(
    expression: str,
    point: str = "0,0",
    variables: str = "x0,x1",
    epsilon: float = _EPS,
) -> str:
    """有限差分计算梯度 ∇L。

    Args:
        expression: 损失表达式，如 x0**2 + x1**2
        point: 逗号分隔坐标，如 0.5,0.5
        variables: 变量名（决定维度）
        epsilon: 差分步长
    """
    try:
        np = _import_numpy()
        var_names = [v.strip() for v in variables.split(",") if v.strip()]
        dim = max(len(var_names), 2)
        x0 = _parse_point(point, dim)
        fn = _loss_fn(expression, dim)
        grad = []
        for i in range(dim):
            xp = list(x0)
            xm = list(x0)
            xp[i] += epsilon
            xm[i] -= epsilon
            g = (fn(xp) - fn(xm)) / (2 * epsilon)
            grad.append(g)
        norm = float(np.linalg.norm(grad))
        return json.dumps(
            {
                "expression": expression,
                "point": x0,
                "gradient": grad,
                "gradient_norm": norm,
                "near_critical": norm < 1e-3,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"expression": expression, "error": str(exc) or "numerical_gradient failed"},
            ensure_ascii=False,
        )


@mcp.tool()
async def hessian_spectrum(
    expression: str,
    point: str = "0,0",
    variables: str = "x0,x1",
    epsilon: float = _EPS,
) -> str:
    """数值 Hessian 及特征值谱。

    Args:
        expression: 标量损失表达式
        point: 评估点坐标
        variables: 变量名列表
        epsilon: 差分步长
    """
    try:
        np = _import_numpy()
        var_names = [v.strip() for v in variables.split(",") if v.strip()]
        dim = max(len(var_names), 2)
        x0 = _parse_point(point, dim)
        fn = _loss_fn(expression, dim)

        def grad_at(x: list[float]) -> list[float]:
            g = []
            for i in range(dim):
                xp, xm = list(x), list(x)
                xp[i] += epsilon
                xm[i] -= epsilon
                g.append((fn(xp) - fn(xm)) / (2 * epsilon))
            return g

        hess = np.zeros((dim, dim))
        for i in range(dim):
            xp, xm = list(x0), list(x0)
            xp[i] += epsilon
            xm[i] -= epsilon
            gi_p = grad_at(xp)
            gi_m = grad_at(xm)
            for j in range(dim):
                hess[i, j] = (gi_p[j] - gi_m[j]) / (2 * epsilon)

        eigenvalues = np.linalg.eigvalsh(hess)
        ev_list = [float(v) for v in eigenvalues]
        all_pos = all(v > 1e-8 for v in ev_list)
        all_neg = all(v < -1e-8 for v in ev_list)
        if all_pos:
            classification = "local_minimum"
        elif all_neg:
            classification = "local_maximum"
        elif any(v > 1e-8 for v in ev_list) and any(v < -1e-8 for v in ev_list):
            classification = "saddle"
        else:
            classification = "degenerate_or_unknown"

        return json.dumps(
            {
                "expression": expression,
                "point": x0,
                "hessian": hess.tolist(),
                "eigenvalues": ev_list,
                "min_eigenvalue": float(min(ev_list)) if ev_list else None,
                "classification": classification,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"expression": expression, "error": str(exc) or "hessian_spectrum failed"},
            ensure_ascii=False,
        )


@mcp.tool()
async def critical_point_classify(
    expression: str,
    point: str = "0,0",
    variables: str = "x0,x1",
) -> str:
    """综合梯度与 Hessian 对临界点分类。"""
    if not (expression or "").strip():
        return json.dumps(
            {"expression": expression, "error": "empty expression"},
            ensure_ascii=False,
        )
    grad_raw = await numerical_gradient(expression, point, variables)
    if not (grad_raw or "").strip():
        return json.dumps(
            {"expression": expression, "error": "empty MCP response"},
            ensure_ascii=False,
        )
    grad_data = json.loads(grad_raw)
    if "error" in grad_data:
        err = grad_data.get("error") or "gradient failed"
        grad_data["error"] = err
        return json.dumps(grad_data, ensure_ascii=False)
    hess_raw = await hessian_spectrum(expression, point, variables)
    if not (hess_raw or "").strip():
        return json.dumps(
            {"expression": expression, "error": "empty MCP response"},
            ensure_ascii=False,
        )
    hess_data = json.loads(hess_raw)
    if "error" in hess_data:
        err = hess_data.get("error") or "hessian failed"
        hess_data["error"] = err
        return json.dumps(hess_data, ensure_ascii=False)
    return json.dumps(
        {
            "expression": expression,
            "point": grad_data["point"],
            "gradient_norm": grad_data["gradient_norm"],
            "near_critical": grad_data["near_critical"],
            "eigenvalues": hess_data["eigenvalues"],
            "classification": hess_data["classification"],
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def loss_landscape_2d(
    expression: str,
    fixed_point: str = "0,0",
    sweep_vars: str = "0,1",
    grid_size: int = 25,
    span: float = 2.0,
) -> str:
    """固定其余维度，扫两维得到 2D loss landscape 网格数据。

    Args:
        expression: 损失表达式（至少含 x0,x1）
        fixed_point: 固定点坐标
        sweep_vars: 要扫的两个维度索引，如 0,1
        grid_size: 每轴网格点数
        span: 扫掠半宽 [-span, span]
    """
    np = _import_numpy()
    try:
        dim = max(len(_parse_point(fixed_point, 2)), 2)
        base = _parse_point(fixed_point, dim)
        idx = [int(s.strip()) for s in sweep_vars.split(",") if s.strip()]
        if len(idx) < 2:
            idx = [0, 1]
        i, j = idx[0], idx[1]
        fn = _loss_fn(expression, dim)
        axis0 = np.linspace(-span, span, grid_size)
        axis1 = np.linspace(-span, span, grid_size)
        z_grid = []
        for a in axis0:
            row = []
            for b in axis1:
                x = list(base)
                while len(x) <= max(i, j):
                    x.append(0.0)
                x[i] = float(a)
                x[j] = float(b)
                row.append(fn(x))
            z_grid.append(row)
        return json.dumps(
            {
                "expression": expression,
                "axis0": axis0.tolist(),
                "axis1": axis1.tolist(),
                "z": z_grid,
                "sweep_dims": [i, j],
                "viz_type": "contour_2d",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"expression": expression, "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
async def sgd_trajectory(
    expression: str = "x0**2 + x1**2",
    start_points: str = "1,1; -1,0.5",
    learning_rate: float = 0.1,
    max_steps: int = 50,
) -> str:
    """从多个初始点运行梯度下降，记录轨迹。

    Args:
        expression: 损失表达式
        start_points: 分号分隔的初始点，如 1,1; -1,0.5
        learning_rate: 学习率
        max_steps: 最大步数
    """
    np = _import_numpy()
    try:
        starts = []
        for seg in start_points.split(";"):
            seg = seg.strip()
            if seg:
                starts.append(_parse_point(seg, 2))
        if not starts:
            starts = [[1.0, 1.0]]
        dim = max(len(s) for s in starts)
        fn = _loss_fn(expression, dim)
        trajectories = []
        for start in starts:
            x = list(start)
            while len(x) < dim:
                x.append(0.0)
            path = [list(x)]
            losses = [fn(x)]
            for _ in range(max_steps):
                grad = []
                for i in range(dim):
                    xp, xm = list(x), list(x)
                    xp[i] += _EPS
                    xm[i] -= _EPS
                    grad.append((fn(xp) - fn(xm)) / (2 * _EPS))
                gnorm = float(np.linalg.norm(grad))
                if gnorm < 1e-6:
                    break
                for i in range(dim):
                    x[i] -= learning_rate * grad[i]
                path.append(list(x))
                losses.append(fn(x))
            trajectories.append(
                {"start": start, "path": path, "losses": losses, "final": x}
            )
        return json.dumps(
            {
                "expression": expression,
                "learning_rate": learning_rate,
                "trajectories": trajectories,
                "viz_type": "sgd_trajectory",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"expression": expression, "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
async def random_hessian_sample(
    expression: str,
    dim: int = 5,
    num_samples: int = 10,
    radius: float = 1.0,
    seed: int = 42,
) -> str:
    """在高维随机点采样 Hessian 最小特征值统计。

    Args:
        expression: 损失表达式（使用 x0..x{dim-1}）
        dim: 维度
        num_samples: 采样点数
        radius: 随机点球半径
        seed: 随机种子
    """
    np = _import_numpy()
    try:
        rng = np.random.default_rng(seed)
        fn = _loss_fn(expression, dim)
        min_eigs = []
        classifications = []
        for _ in range(num_samples):
            direction = rng.standard_normal(dim)
            direction = direction / (np.linalg.norm(direction) + 1e-12)
            point = (direction * radius * rng.random()).tolist()
            hess_raw = await hessian_spectrum(
                expression,
                ",".join(str(v) for v in point),
                ",".join(f"x{i}" for i in range(dim)),
            )
            data = json.loads(hess_raw)
            if "error" in data:
                continue
            min_eigs.append(data.get("min_eigenvalue"))
            classifications.append(data.get("classification"))
        return json.dumps(
            {
                "expression": expression,
                "dim": dim,
                "num_samples": len(min_eigs),
                "min_eigenvalues": min_eigs,
                "classifications": classifications,
                "saddle_fraction": sum(
                    1 for c in classifications if c == "saddle"
                )
                / max(len(classifications), 1),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"expression": expression, "error": str(exc)}, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

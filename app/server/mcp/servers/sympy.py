# MCP Server：SymPy 符号计算（简化、求导、求解）。

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sympy")


def _import_sympy():
    try:
        import sympy as sp
    except ImportError as exc:
        raise RuntimeError(
            "SymPy 未安装。请执行: pip install sympy"
        ) from exc
    return sp


@mcp.tool()
async def simplify_expression(expression: str) -> str:
    """化简数学表达式。

    Args:
        expression: SymPy 可解析的表达式，如 (x+1)**2 - x**2 - 2*x
    """
    sp = _import_sympy()
    try:
        expr = sp.sympify(expression)
        simplified = sp.simplify(expr)
        return json.dumps(
            {
                "input": expression,
                "result": str(simplified),
                "latex": sp.latex(simplified),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"input": expression, "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
async def differentiate(expression: str, variable: str = "x") -> str:
    """对表达式求导。

    Args:
        expression: 可解析表达式
        variable: 求导变量名
    """
    sp = _import_sympy()
    try:
        expr = sp.sympify(expression)
        var = sp.symbols(variable)
        derivative = sp.diff(expr, var)
        return json.dumps(
            {
                "input": expression,
                "variable": variable,
                "result": str(derivative),
                "latex": sp.latex(derivative),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"input": expression, "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
async def solve_equation(equation: str, variable: str = "x") -> str:
    """求解方程或表达式等于零。

    Args:
        equation: 方程如 x**2 - 1 = 0 或表达式 x**2 - 1
        variable: 求解变量
    """
    sp = _import_sympy()
    try:
        var = sp.symbols(variable)
        if "=" in equation:
            left, right = equation.split("=", 1)
            eq = sp.Eq(sp.sympify(left), sp.sympify(right))
        else:
            eq = sp.sympify(equation)
        solutions = sp.solve(eq, var)
        return json.dumps(
            {
                "input": equation,
                "variable": variable,
                "solutions": [str(s) for s in solutions],
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"input": equation, "error": str(exc)}, ensure_ascii=False)


def _parse_variables(variables: str, sp) -> list:
    """Parse comma-separated variable names into SymPy symbols."""
    names = [v.strip() for v in variables.split(",") if v.strip()]
    if not names:
        names = ["x"]
    return list(sp.symbols(",".join(names)))


@mcp.tool()
async def hessian_eigenvalues(expression: str, variables: str = "x") -> str:
    """计算 Hessian 矩阵及特征值，判断临界点类型。

    Args:
        expression: 标量损失函数表达式，如 x**2 + y**2
        variables: 逗号分隔变量名，如 x,y 或 theta1,theta2
    """
    sp = _import_sympy()
    try:
        expr = sp.sympify(expression)
        vars_list = _parse_variables(variables, sp)
        if len(vars_list) == 1:
            hessian = sp.Matrix([[sp.diff(expr, vars_list[0], 2)]])
        else:
            hessian = sp.hessian(expr, vars_list)
        eigenvals = hessian.eigenvals()
        eigen_list = []
        for val, mult in eigenvals.items():
            try:
                val_float = float(sp.N(val))
            except (TypeError, ValueError):
                val_float = None
            eigen_list.append({"value": str(val), "multiplicity": mult, "numeric": val_float})
        all_positive = all(
            e.get("numeric") is not None and e["numeric"] > 1e-10 for e in eigen_list
        ) if eigen_list else False
        all_negative = all(
            e.get("numeric") is not None and e["numeric"] < -1e-10 for e in eigen_list
        ) if eigen_list else False
        if all_positive:
            classification = "local_minimum"
        elif all_negative:
            classification = "local_maximum"
        elif eigen_list:
            classification = "saddle_or_indefinite"
        else:
            classification = "unknown"
        return json.dumps(
            {
                "input": expression,
                "variables": variables,
                "hessian": str(hessian),
                "eigenvalues": eigen_list,
                "classification": classification,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"input": expression, "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
async def taylor_expand(
    expression: str,
    variable: str = "x",
    point: str = "0",
    order: int = 3,
) -> str:
    """在指定点作 Taylor 展开。

    Args:
        expression: 可解析表达式
        variable: 展开变量名
        point: 展开点，如 0 或 theta_star
        order: 展开阶数（默认 3）
    """
    sp = _import_sympy()
    try:
        expr = sp.sympify(expression)
        var = sp.symbols(variable)
        pt = sp.sympify(point)
        series = sp.series(expr, var, pt, order + 1).removeO()
        return json.dumps(
            {
                "input": expression,
                "variable": variable,
                "point": point,
                "order": order,
                "result": str(series),
                "latex": sp.latex(series),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"input": expression, "error": str(exc)}, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

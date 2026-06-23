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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

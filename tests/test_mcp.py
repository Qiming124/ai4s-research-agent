"""SymPy MCP Server 单元测试。"""

import json

import pytest

from server.mcp.servers import sympy as sympy_server


@pytest.fixture
def sp():
    return sympy_server._import_sympy()


@pytest.mark.asyncio
async def test_simplify_expression():
    result = await sympy_server.simplify_expression("(x+1)**2 - x**2 - 2*x")
    data = json.loads(result)
    assert "error" not in data
    assert data["result"] == "1"


@pytest.mark.asyncio
async def test_differentiate():
    result = await sympy_server.differentiate("x**2", "x")
    data = json.loads(result)
    assert data["result"] == "2*x"


@pytest.mark.asyncio
async def test_hessian_eigenvalues_quadratic():
    result = await sympy_server.hessian_eigenvalues("x**2 + y**2", "x,y")
    data = json.loads(result)
    assert "error" not in data
    assert data["classification"] == "local_minimum"
    assert len(data["eigenvalues"]) >= 1


@pytest.mark.asyncio
async def test_hessian_eigenvalues_saddle():
    result = await sympy_server.hessian_eigenvalues("x**2 - y**2", "x,y")
    data = json.loads(result)
    assert "error" not in data
    assert data["classification"] == "saddle_or_indefinite"


@pytest.mark.asyncio
async def test_taylor_expand():
    result = await sympy_server.taylor_expand("exp(x)", "x", "0", 3)
    data = json.loads(result)
    assert "error" not in data
    assert "x" in data["result"]

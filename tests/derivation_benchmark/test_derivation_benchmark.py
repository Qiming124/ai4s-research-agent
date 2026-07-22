"""推导质量回归：数值临界点分类基准。"""

import json
from pathlib import Path

import pytest

CASES_PATH = Path(__file__).parent / "cases.json"


@pytest.fixture
def cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_critical_point_benchmark(cases: list[dict]):
    from server.mcp.servers import numerical as num_mod

    passed = 0
    for case in cases:
        raw = await num_mod.critical_point_classify(
            case["expression"],
            case["point"],
            "x0,x1",
        )
        data = json.loads(raw)
        if data.get("classification") == case["expected_classification"]:
            passed += 1
    rate = passed / len(cases) if cases else 0
    assert rate >= 0.8, f"benchmark pass rate {rate:.0%} < 80%"


def test_theory_workspace_loads():
    from server.memory.theory_workspace import load_symbols, load_assumptions

    symbols = load_symbols()
    assumptions = load_assumptions()
    assert "L" in symbols or "损失" in symbols
    assert "A1" in assumptions or "光滑" in assumptions



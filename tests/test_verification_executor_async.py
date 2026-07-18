# 验证执行器 / 异步工具回归。

from __future__ import annotations

import asyncio
import json

import pytest


def test_run_coro_sync_without_running_loop():
    from server.experiments.async_utils import run_coro_sync

    async def _add(a: int, b: int) -> int:
        return a + b

    assert run_coro_sync(_add(1, 2)) == 3


@pytest.mark.asyncio
async def test_run_coro_sync_with_running_loop():
    from server.experiments.async_utils import run_coro_sync

    async def _add(a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a + b

    # 有 running loop 时不得抛 "Cannot run the event loop while another loop is running"
    assert run_coro_sync(_add(2, 3)) == 5


@pytest.mark.asyncio
async def test_execute_claim_verification_quadratic(monkeypatch):
    from server.experiments import verification_executor as ve

    class _FakeMcp:
        async def call_tool(self, name: str, arguments: dict) -> str:
            assert name == "numerical__critical_point_classify"
            return json.dumps(
                {
                    "expression": arguments["expression"],
                    "point": [0.0, 0.0],
                    "gradient_norm": 0.0,
                    "near_critical": True,
                    "eigenvalues": [2.0, 2.0],
                    "classification": "local_minimum",
                }
            )

    async def _fake_client():
        return _FakeMcp()

    monkeypatch.setattr(ve, "get_mcp_client", _fake_client)
    result = await ve.execute_claim_verification(
        {
            "expression": "x0**2 + x1**2",
            "point": "0,0",
            "variables": "x0,x1",
            "expected": {"classification": "local_minimum"},
            "tier_hint": "numerical",
        },
        session_id="test-exec-quad",
    )
    assert result["overall_passed"] is True
    assert result["tiers"]["symbolic"]["status"] == "skipped"
    assert result["tiers"]["numerical"]["status"] == "pass"
    assert result["tiers"]["numerical"]["reason"]


@pytest.mark.asyncio
async def test_execute_claim_verification_empty_mcp_reason(monkeypatch):
    from server.experiments import verification_executor as ve

    class _FakeMcp:
        async def call_tool(self, name: str, arguments: dict) -> str:
            return json.dumps({"error": ""})

    async def _fake_client():
        return _FakeMcp()

    monkeypatch.setattr(ve, "get_mcp_client", _fake_client)
    result = await ve.execute_claim_verification(
        {
            "expression": "x0**2",
            "point": "0",
            "variables": "x0",
            "tier_hint": "numerical",
        },
        session_id="test-empty-reason",
    )
    assert result["tiers"]["numerical"]["status"] == "fail"
    assert result["tiers"]["numerical"]["reason"]
    assert result["tiers"]["numerical"]["reason"] != ""

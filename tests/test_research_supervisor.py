# ResearchSupervisor 与 Campaign 实验单元测试。

from __future__ import annotations

import json

import pytest

from server.experiments.campaign_experiments import (
    build_symbolic_config,
    run_campaign_experiments,
    _mentions_overparameterization,
)
from server.graph.research_supervisor import _check_gate, _build_context_pack
from server.memory.campaigns import get_campaign_store


def test_demo_campaign_seed():
    store = get_campaign_store()
    camp = store.get_campaign("pl-critical-points-demo")
    assert camp is not None
    assert camp["task_family"] == "loss_landscape_critical_points"
    assert "A4" in camp["assumptions"]


def test_campaign_create_and_artifact(tmp_path, monkeypatch):
    store = get_campaign_store()
    camp = store.create_campaign("default", title="单元测试 Campaign")
    updated = store.save_stage_artifact(
        camp["id"],
        "S0_campaign",
        {"summary": "test"},
        persist_file=True,
    )
    assert updated is not None
    assert "S0_campaign" in updated["stage_artifacts"]


def test_build_symbolic_config():
    cfg = build_symbolic_config("theta**2 + x1**2")
    assert "x0" in cfg["expression"] or "theta" in cfg["expression"]
    assert cfg["expected"]["classification"] == "local_minimum"


def test_mentions_overparameterization():
    assert _mentions_overparameterization("浅层 MLP width scaling A5")
    assert not _mentions_overparameterization("二次损失 x^2")


@pytest.mark.asyncio
async def test_run_campaign_experiments_quadratic(monkeypatch):
    async def _fake_verify(claim, **kwargs):
        return {
            "overall_passed": True,
            "tiers": {
                "symbolic": {"status": "skipped", "reason": "tier_hint=numerical"},
                "numerical": {
                    "status": "pass",
                    "reason": "分类=local_minimum",
                    "passed": True,
                },
            },
        }

    monkeypatch.setattr(
        "server.experiments.campaign_experiments.execute_claim_verification",
        _fake_verify,
    )
    result = await run_campaign_experiments(
        "损失 L = x0**2 + x1**2 在 (0,0) 处为局部极小",
        session_id="test-supervisor",
        campaign={"compute_budget": {"max_torch_runs": 0}},
    )
    assert "runs" in result
    assert result["quadratic_pass"] is True
    assert result["summary"]["status"] == "pass"
    assert result["summary"].get("reason")


@pytest.mark.asyncio
async def test_run_campaign_experiments_status_vocab(monkeypatch):
    """成功时 executor 返回 completed/overall_passed，不得误判为 fail。"""

    async def _fake_verify(claim, **kwargs):
        return {
            "overall_passed": True,
            "status": "completed",
            "tiers": {
                "numerical": {"status": "pass", "reason": "分类=local_minimum"},
            },
        }

    monkeypatch.setattr(
        "server.experiments.campaign_experiments.execute_claim_verification",
        _fake_verify,
    )
    result = await run_campaign_experiments(
        "L = x0**2 + x1**2",
        session_id="test-status-vocab",
        campaign={"compute_budget": {"max_torch_runs": 0}},
    )
    assert result["quadratic_pass"] is True
    assert any(
        (r.get("result") or {}).get("status") in ("completed", "pass")
        or (r.get("result") or {}).get("overall_passed") is True
        for r in result["runs"]
        if "result" in r
    )


def test_is_quad_success_accepts_completed():
    from server.experiments.campaign_experiments import _is_quad_success

    assert _is_quad_success({"status": "completed", "overall_passed": True})
    assert _is_quad_success(
        {"summary": {"overall_passed": True, "tiers": {"numerical": {"status": "pass"}}}}
    )
    assert not _is_quad_success({"status": "failed", "overall_passed": False})


def test_check_gates():
    status, reason = _check_gate(
        "S1_literature",
        {"summary": "综述", "reference_count": 2},
        None,
    )
    assert status == "pass"

    status2, _ = _check_gate(
        "S3_theory",
        {"verification_status": "pass", "summary": "定理"},
        None,
    )
    assert status2 == "pass"

    status3, _ = _check_gate(
        "S7_review",
        {"summary": "存在致命缺陷：证明不完整"},
        None,
    )
    assert status3 == "fail"

    # 误报回归：正文回顾「致命」但结论为有条件通过
    status4, reason4 = _check_gate(
        "S7_review",
        {
            "summary": (
                "审稿建议：**通过（有条件）**——致命问题已修复，剩余问题为次要。\n"
                "第一轮指出的致命错误已在第二轮修复。"
            ),
        },
        None,
    )
    assert status4 == "pass", reason4

    status5, _ = _check_gate(
        "S7_review",
        {"summary": "综合意见良好，建议接受并做 minor revision。"},
        None,
    )
    assert status5 == "pass"


def test_context_pack():
    camp = {
        "id": "x",
        "title": "T",
        "assumptions": ["A1"],
        "task_family": "f",
        "dataset": "d",
        "benchmark": "b",
        "stage_artifacts": {
            "S1_literature": {"summary": "lit"},
            "S2_formalization": {"summary": "prob"},
        },
    }
    pack = _build_context_pack(camp)
    assert pack["literature_digest"]["summary"] == "lit"
    assert pack["problem_statement"]["summary"] == "prob"


def test_research_pipeline_mode_detection():
    from server.config import Settings
    from server.graph.research_pipeline import should_use_research_pipeline

    settings = Settings(deepseek_api_key="sk-test", research_pipeline_mode="single")
    assert not should_use_research_pipeline("证明局部极小", "math", settings)

    settings_auto = Settings(deepseek_api_key="sk-test", research_pipeline_mode="auto")
    assert should_use_research_pipeline("证明局部极小值定理", "math", settings_auto)
    assert should_use_research_pipeline("/research PL条件", "chat", settings_auto)

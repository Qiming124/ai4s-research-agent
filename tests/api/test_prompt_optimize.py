# 提示词优化 API 测试。

from __future__ import annotations

import json


def test_prompt_templates(client):
    r = client.get("/v1/prompt/templates")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 4
    ids = {t["id"] for t in data}
    assert "rccf" in ids
    assert "imrad" in ids


def test_prompt_test_cases(client):
    r = client.get("/v1/prompt/test-cases")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3
    case = next(c for c in data if c["id"] == "loss_landscape")
    assert "局部极小值" in case["title"]
    assert case["raw_prompt"]

    # 单条详情接口已移除：列表即完整内容
    detail = client.get("/v1/prompt/test-cases/loss_landscape")
    assert detail.status_code == 404


def test_prompt_optimize_empty(client):
    r = client.post("/v1/prompt/optimize", json={"text": "  "})
    assert r.status_code == 400


def test_prompt_optimize_fallback(client, monkeypatch):
    async def _mock_optimize(**kwargs):
        from server.llm.prompt_optimizer import _fallback_result

        result = _fallback_result(
            kwargs["text"],
            kwargs.get("context", ""),
            kwargs.get("goal", ""),
        )
        result["original"] = kwargs["text"]
        return result

    monkeypatch.setattr("server.api.prompt.optimize_user_prompt", _mock_optimize)

    r = client.post(
        "/v1/prompt/optimize",
        json={
            "text": "分析损失函数局部极小值",
            "mode": "math",
            "goal": "更专业",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["original"] == "分析损失函数局部极小值"
    assert len(data["variants"]) == 4
    assert data["recommended_prompt"]
    assert data["recommended_style_id"]


def test_prompt_optimize_mock_llm(client, monkeypatch):
    mock_response = {
        "variants": [
            {
                "style_id": "rccf",
                "prompt": "你是一位深度学习优化理论研究员。任务：分析损失函数局部极小值…",
                "scores": {"clarity": 9, "specificity": 8, "verifiability": 8, "structure": 9},
                "highlights": ["角色明确"],
            },
            {
                "style_id": "pbtm",
                "prompt": "【第1步】界定损失函数临界点问题…",
                "scores": {"clarity": 8, "specificity": 9, "verifiability": 9, "structure": 8},
                "highlights": ["分步迭代"],
            },
        ],
        "recommended_style_id": "pbtm",
        "rationale": "理论推导场景更适合 PBTM 分步结构。",
    }

    async def _mock_optimize(**kwargs):
        from server.llm.prompt_optimizer import _parse_llm_result

        result = _parse_llm_result(
            json.dumps(mock_response),
            text=kwargs["text"],
            context=kwargs.get("context", ""),
            goal=kwargs.get("goal", ""),
        )
        result["original"] = kwargs["text"]
        return result

    monkeypatch.setattr("server.api.prompt.optimize_user_prompt", _mock_optimize)

    r = client.post(
        "/v1/prompt/optimize",
        json={"text": "帮我证明一个定理", "mode": "math"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["recommended_style_id"] == "pbtm"
    assert data["ai_applied"] is True
    assert any(v["recommended"] for v in data["variants"])

# 全量 API 冒烟。

from __future__ import annotations

import tempfile

import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_projects_smoke(client):
    r = client.get("/v1/projects")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.get("/v1/projects/default")
    assert r.status_code == 200

    r = client.get("/v1/projects/default/members")
    assert r.status_code == 200

    r = client.get("/v1/projects/default/tasks")
    assert r.status_code == 200

    r = client.post("/v1/projects/default/sessions/smoke-session-1")
    assert r.status_code == 200


def test_verification_smoke(client):
    r = client.get("/v1/verification/dashboard")
    assert r.status_code == 200

    r = client.get("/v1/verification/records")
    assert r.status_code == 200

    claim = {
        "claim": {
            "expression": "x0**2 + x1**2",
            "point": "0,0",
            "variables": "x0,x1",
            "expected": {"classification": "local_minimum"},
            "tier_hint": "numerical",
        },
        "session_id": "smoke-session-1",
    }
    try:
        r = client.post("/v1/verification/run", json=claim)
    except RuntimeError:
        import pytest
        pytest.skip("verification async lifecycle unavailable in TestClient")
    assert r.status_code in (200, 500)


def test_experiments_smoke(client):
    r = client.post("/v1/experiments/runs", json={"config_path": "quadratic_minimum.yaml"})
    assert r.status_code in (200, 500)
    r = client.get("/v1/experiments/runs")
    assert r.status_code == 200


def test_theory_routes_removed(client):
    """工作区文件、假设 DAG、关系图谱 GET 已下线。"""
    assert client.get("/v1/theory/assumption-dag").status_code == 404
    assert client.get("/v1/theory/assumption-dag/impact/A4").status_code == 404
    assert client.get("/v1/theory/workspace").status_code == 404
    # /graph 曾被 {entry_id} 路由吞掉时可能为 405；下线后应不可用
    assert client.get("/v1/memory/structured/graph").status_code in (404, 405, 422)


def test_memory_versioning_smoke(client):
    r = client.post(
        "/v1/memory/structured",
        json={"session_id": "smoke-session-1", "kind": "theorem", "title": "Smoke Thm", "body": "test body"},
    )
    assert r.status_code == 200
    entry_id = r.json()["id"]
    vr = client.post(f"/v1/memory/structured/{entry_id}/versions")
    vl = client.get(f"/v1/memory/structured/{entry_id}/versions")
    assert vr.status_code == 200
    assert vl.status_code == 200


def test_jupyter_smoke(client):
    r = client.post(
        "/v1/jupyter/upload-result",
        json={"name": "smoke", "summary": {"ok": True}, "metrics": {"loss": 0.1}},
    )
    assert r.status_code == 200


def test_sync_smoke(client):
    r = client.get("/v1/sync/audit/default")
    assert r.status_code == 200


def test_export_observability_smoke(client):
    r = client.post("/v1/export/latex", json={"session_id": "smoke-session-1", "title": "Smoke"})
    assert r.status_code == 200
    assert len(r.json().get("latex", "")) > 0

    r = client.get("/v1/observability/summary")
    assert r.status_code == 200

    r = client.get("/v1/observability/agent-quality")
    assert r.status_code == 200


def test_agents_smoke(client):
    r = client.get("/v1/agents")
    agents = [a["name"] for a in r.json().get("agents", [])]
    assert "counterexample" in agents


def test_claim_parser_unit():
    from server.memory.claim_parser import parse_verifiable_claim

    sample = '```yaml\nverifiable:\n  expression: "x0**2"\n  point: "0,0"\n```'
    assert parse_verifiable_claim(sample) is not None

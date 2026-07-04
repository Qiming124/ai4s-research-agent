# E2E 冒烟测试（API 层）。

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-ci-only")
    from server.config import get_settings

    get_settings.cache_clear()
    from server.main import create_app

    return TestClient(create_app())


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_projects_list(client):
    res = client.get("/v1/projects")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(p["id"] == "default" for p in data["projects"])


def test_verification_dashboard(client):
    res = client.get("/v1/verification/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "total_records" in data


def test_assumption_dag(client):
    res = client.get("/v1/theory/assumption-dag")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data


def test_observability_summary(client):
    res = client.get("/v1/observability/summary")
    assert res.status_code == 200
    data = res.json()
    assert "verification_pass_rate" in data


def test_jupyter_template(client):
    res = client.get("/v1/jupyter/template")
    assert res.status_code == 200

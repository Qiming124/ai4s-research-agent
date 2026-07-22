# Artifact API 冒烟

from __future__ import annotations

from fastapi.testclient import TestClient


def test_artifacts_create_and_list(monkeypatch, tmp_path):
    from shared.paths import DATA_ROOT
    import server.artifacts.store as store_mod

    # 将 store 指到临时目录
    store_mod._store = store_mod.ArtifactStore(root=tmp_path / "projects")

    from server.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/artifacts",
        json={
            "type": "ExperimentPlan",
            "project_id": "default",
            "data": {
                "title": "plan-a",
                "objectives": "测 Hessian",
                "variables": ["lr"],
                "success_criteria": ["谱为正"],
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "ExperimentPlan"
    aid = body["data"]["id"]

    listed = client.get("/v1/artifacts", params={"project_id": "default", "types": "ExperimentPlan"})
    assert listed.status_code == 200
    arts = listed.json()["artifacts"]
    assert any(a["id"] == aid for a in arts)

    detail = client.get(f"/v1/artifacts/{aid}", params={"project_id": "default"})
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "plan-a"

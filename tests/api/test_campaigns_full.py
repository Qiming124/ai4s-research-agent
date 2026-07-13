# Campaign API 全量测试。

from __future__ import annotations


def test_get_demo_campaign_by_id(client):
    r = client.get("/v1/projects/default/campaigns/pl-critical-points-demo")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "pl-critical-points-demo"
    assert data["project_id"] == "default"
    assert "A1" in data["assumptions"]


def test_get_active_campaign(client):
    r = client.get("/v1/projects/default/campaign")
    assert r.status_code == 200
    data = r.json()
    assert data["project_id"] == "default"
    assert data["status"] in ("active", "blocked", "iterate", "done")


def test_list_campaigns(client):
    r = client.get("/v1/projects/default/campaigns")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_create_and_get_campaign(client):
    r = client.post(
        "/v1/projects/default/campaign",
        json={
            "title": "测试 Campaign",
            "assumptions": ["A1", "A4"],
            "dataset": "quadratic",
        },
    )
    assert r.status_code == 200
    cid = r.json()["id"]
    assert r.json()["title"] == "测试 Campaign"

    r2 = client.get(f"/v1/projects/default/campaigns/{cid}")
    assert r2.status_code == 200
    assert r2.json()["assumptions"] == ["A1", "A4"]


def test_update_campaign_stage(client):
    r = client.get("/v1/projects/default/campaign")
    cid = r.json()["id"]
    r2 = client.patch(
        f"/v1/projects/default/campaigns/{cid}",
        json={"current_stage": "S1_literature", "status": "active"},
    )
    assert r2.status_code == 200
    assert r2.json()["current_stage"] == "S1_literature"

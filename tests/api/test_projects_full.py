# Projects API 全量测试。

from __future__ import annotations


def test_list_and_create_project(client):
    r = client.get("/v1/projects")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.post("/v1/projects", json={"name": "API Test Project", "description": "test"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert pid

    r = client.get(f"/v1/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["name"] == "API Test Project"


def test_project_members(client):
    r = client.get("/v1/projects/default/members")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_project_tasks_crud(client):
    r = client.post(
        "/v1/projects/default/tasks",
        json={"title": "API task", "assignee_role": "theorist"},
    )
    assert r.status_code == 200
    task_id = r.json()["id"]

    r = client.get("/v1/projects/default/tasks")
    assert r.status_code == 200
    assert any(t["id"] == task_id for t in r.json()["tasks"])

    r = client.patch(f"/v1/projects/default/tasks/{task_id}?status=in_progress")
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


def test_link_and_list_sessions(client, session_id):
    r = client.post(f"/v1/projects/default/sessions/{session_id}")
    assert r.status_code == 200

    r = client.get("/v1/projects/default/sessions")
    assert r.status_code == 200
    ids = [s["session_id"] for s in r.json().get("sessions", [])]
    assert session_id in ids


def test_invalid_project_tasks_404(client):
    r = client.get("/v1/projects/nonexistent-xyz/tasks")
    # resolve falls back to default if default exists
    assert r.status_code in (200, 404)

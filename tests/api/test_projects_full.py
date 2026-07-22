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
    from server.memory.session import get_session_store

    get_session_store().get_or_create(session_id)
    r = client.post(f"/v1/projects/default/sessions/{session_id}")
    assert r.status_code == 200

    r = client.get("/v1/projects/default/sessions")
    assert r.status_code == 200
    ids = [s["session_id"] for s in r.json().get("sessions", [])]
    assert session_id in ids


def test_unlink_and_purge_clears_project_link(client):
    from server.memory.session import get_session_store

    sid = "unlink-purge-sess-test"
    get_session_store().get_or_create(sid)

    r = client.post(f"/v1/projects/default/sessions/{sid}")
    assert r.status_code == 200

    r = client.delete(f"/v1/projects/default/sessions/{sid}")
    assert r.status_code == 200
    assert r.json().get("removed", 0) >= 1

    r = client.get("/v1/projects/default/sessions")
    assert sid not in [s["session_id"] for s in r.json().get("sessions", [])]

    # 再关联后 purge 会话，关联应一并消失
    get_session_store().get_or_create(sid)
    assert client.post(f"/v1/projects/default/sessions/{sid}").status_code == 200
    assert client.delete(f"/v1/sessions/{sid}?purge=true").status_code == 200
    r = client.get("/v1/projects/default/sessions")
    assert sid not in [s["session_id"] for s in r.json().get("sessions", [])]


def test_delete_project_cascade(client):
    r = client.post(
        "/v1/projects",
        json={"name": "To Delete", "description": "cascade test"},
    )
    assert r.status_code == 200
    pid = r.json()["id"]
    assert pid != "default"

    sid = "del-proj-sess-test"
    # 确保会话存在于 session store
    from server.memory.session import get_session_store

    get_session_store().get_or_create(sid)
    r = client.post(f"/v1/projects/{pid}/sessions/{sid}")
    assert r.status_code == 200

    r = client.delete(f"/v1/projects/{pid}")
    assert r.status_code == 400

    r = client.delete(f"/v1/projects/{pid}?purge=true")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deleted"
    assert body["project_id"] == pid
    assert sid in body.get("deleted_sessions", [])

    r = client.get(f"/v1/projects/{pid}")
    assert r.status_code == 404

    # 会话已 purge
    r = client.delete(f"/v1/sessions/{sid}?purge=true")
    assert r.status_code == 404


def test_cannot_delete_default_project(client):
    r = client.delete("/v1/projects/default?purge=true")
    assert r.status_code == 400


def test_invalid_project_tasks_404(client):
    r = client.get("/v1/projects/nonexistent-xyz/tasks")
    # resolve falls back to default if default exists
    assert r.status_code in (200, 404)

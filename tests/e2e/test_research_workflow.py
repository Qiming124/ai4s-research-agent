# 黄金路径：课题 → 会话关联 → 记忆 → 导出。

from __future__ import annotations


def test_research_gold_path(client):
    r = client.get("/v1/projects/default")
    assert r.status_code == 200

    from server.memory.session import get_session_store

    sid = "e2e-gold-path"
    get_session_store().get_or_create(sid)
    r = client.post(f"/v1/projects/default/sessions/{sid}")
    assert r.status_code == 200

    r = client.post(
        "/v1/memory/structured",
        json={
            "session_id": sid,
            "kind": "theorem",
            "title": "E2E Thm",
            "body": "∇L=0 and H ≽ 0 ⇒ local min.",
        },
    )
    assert r.status_code == 200

    r = client.get("/v1/memory/structured", params={"session_id": sid})
    assert r.status_code == 200
    assert r.json().get("total", 0) >= 1

    r = client.post("/v1/export/latex", json={"session_id": sid, "title": "E2E"})
    assert r.status_code == 200
    assert len(r.json().get("latex", "")) > 0

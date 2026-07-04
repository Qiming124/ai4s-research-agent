# Chat & Sessions API 测试。

from __future__ import annotations


def test_list_sessions(client):
    r = client.get("/v1/sessions")
    assert r.status_code == 200
    assert "sessions" in r.json()


def test_get_empty_session(client, session_id):
    r = client.get(f"/v1/sessions/{session_id}")
    assert r.status_code in (200, 404)


def test_delete_session_clear(client, session_id):
    r = client.delete(f"/v1/sessions/{session_id}")
    assert r.status_code == 200


def test_mcp_status(client):
    try:
        r = client.get("/v1/mcp/status")
    except RuntimeError:
        import pytest
        pytest.skip("MCP lifecycle unavailable in TestClient")
    assert r.status_code == 200


def test_stats_tokens(client, session_id):
    r = client.get(f"/v1/stats/tokens?session_id={session_id}")
    assert r.status_code == 200

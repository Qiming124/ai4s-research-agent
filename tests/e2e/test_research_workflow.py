# 黄金路径：课题 → Campaign → 文献 → 验证 → 导出。

from __future__ import annotations


def test_research_workflow_golden_path(client, session_id):
    # 0. Campaign 示范课题
    r = client.get("/v1/projects/default/campaigns/pl-critical-points-demo")
    assert r.status_code == 200
    campaign_id = r.json()["id"]

    # 1. 关联会话到课题
    r = client.post(f"/v1/projects/default/sessions/{session_id}")
    assert r.status_code == 200

    # 2. 文本文献入库
    r = client.post(
        "/v1/documents",
        json={
            "session_id": session_id,
            "content": "Local minima in neural network loss landscapes.",
            "title": "Workflow Doc",
        },
    )
    if r.status_code == 400:
        pass  # RAG disabled ok for workflow
    else:
        assert r.status_code == 200

    # 3. 结构化记忆（定理）
    r = client.post(
        "/v1/memory/structured",
        json={
            "session_id": session_id,
            "kind": "theorem",
            "title": "Workflow Theorem",
            "body": "f has local minimum at x*.",
        },
    )
    assert r.status_code == 200

    # 4. 验证仪表盘
    r = client.get(f"/v1/verification/dashboard?session_id={session_id}")
    assert r.status_code == 200

    # 5. 导出 LaTeX
    r = client.post(
        "/v1/export/latex",
        json={"session_id": session_id, "title": "Workflow Export", "project_id": "default"},
    )
    assert r.status_code == 200
    assert "Workflow" in r.json()["latex"] or "\\title" in r.json()["latex"]

    # 6. 课题会话列表
    r = client.get("/v1/projects/default/sessions")
    assert r.status_code == 200
    ids = [s["session_id"] for s in r.json().get("sessions", [])]
    assert session_id in ids

    # 7. Campaign 阶段可更新
    r = client.patch(
        f"/v1/projects/default/campaigns/{campaign_id}",
        json={"current_stage": "S3_theory"},
    )
    assert r.status_code == 200
    assert r.json()["current_stage"] == "S3_theory"

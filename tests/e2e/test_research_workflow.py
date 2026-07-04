# 黄金路径：课题 → 文献 → 验证 → 导出。

from __future__ import annotations


def test_research_workflow_golden_path(client, session_id):
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

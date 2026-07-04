# Export API 测试。

from __future__ import annotations


def test_export_preview_empty(client):
    r = client.get("/v1/export/preview?session_id=nonexistent-session")
    assert r.status_code == 200
    data = r.json()
    assert data["entry_count"] == 0
    assert data["source"] == "empty"


def test_export_latex(client, session_id):
    r = client.post(
        "/v1/export/latex",
        json={"session_id": session_id, "title": "Test", "project_id": "default"},
    )
    assert r.status_code == 200
    assert "\\documentclass" in r.json()["latex"]


def test_export_markdown(client, session_id):
    client.post(
        "/v1/memory/structured",
        json={
            "session_id": session_id,
            "kind": "theorem",
            "title": "测试定理",
            "body": "损失函数 L(θ) 在 θ=0 处取得局部极小值。",
        },
    )
    r = client.post(
        "/v1/export/md",
        json={"session_id": session_id, "title": "中文测试", "project_id": "default"},
    )
    assert r.status_code == 200
    text = r.content.decode("utf-8")
    assert "# 中文测试" in text
    assert "## 定理：测试定理" in text
    assert "损失函数" in text


def test_export_docx(client, session_id):
    r = client.post(
        "/v1/export/docx",
        json={"session_id": session_id, "title": "Test", "project_id": "default"},
    )
    assert r.status_code == 200
    assert len(r.content) > 100


def test_export_pdf(client, session_id):
    r = client.post(
        "/v1/export/pdf",
        json={"session_id": session_id, "title": "测试论文", "project_id": "default"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1000


def test_export_pdf_chinese_entries(client, session_id):
    client.post(
        "/v1/memory/structured",
        json={
            "session_id": session_id,
            "kind": "note",
            "title": "测试引理",
            "body": "损失函数 L(θ) 在 θ=0 处取得局部极小值。",
        },
    )
    r = client.post(
        "/v1/export/pdf",
        json={"session_id": session_id, "title": "中文测试", "project_id": "default"},
    )
    if r.status_code == 503:
        import pytest

        pytest.skip(r.text[:200])
    assert r.status_code == 200
    assert len(r.content) > 1500
    try:
        from pypdf import PdfReader
        import io

        text = "".join(
            (p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages
        )
        assert "损失函数" in text or "极小值" in text
    except ImportError:
        pass


def test_export_polish_requires_instructions(client, session_id):
    r = client.post(
        "/v1/export/polish",
        json={"session_id": session_id, "title": "Test", "project_id": "default"},
    )
    assert r.status_code == 400


def test_export_polish_with_mock(client, session_id, monkeypatch):
    client.post(
        "/v1/memory/structured",
        json={
            "session_id": session_id,
            "kind": "theorem",
            "title": "原定理",
            "body": "损失函数在零点处取极小值。",
        },
    )

    async def _fake_polish(**kwargs):
        return "# AI 修订稿\n\n## 定理：润色后\n\n损失函数在零点处取极小值。\n", True

    monkeypatch.setattr("server.api.export.polish_export_markdown", _fake_polish)

    r = client.post(
        "/v1/export/polish",
        json={
            "session_id": session_id,
            "title": "AI 测试",
            "project_id": "default",
            "use_ai": True,
            "ai_instructions": "改成更学术的语气",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ai_applied"] is True
    assert "润色后" in data["markdown"]

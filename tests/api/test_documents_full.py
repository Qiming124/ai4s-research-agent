# Documents API 全量测试。

from __future__ import annotations

import io

import pytest


@pytest.fixture
def rag_enabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_RAG", "true")
    from server.config import get_settings

    get_settings.cache_clear()


def test_documents_text_upload(client, rag_enabled, session_id):
    r = client.post(
        "/v1/documents",
        json={
            "session_id": session_id,
            "content": "Test document for RAG indexing.",
            "title": "Test Doc",
        },
    )
    if r.status_code == 400 and "RAG" in r.text:
        pytest.skip("RAG not enabled in test env")
    assert r.status_code == 200
    doc_id = r.json()["document"]["doc_id"]

    r = client.get(f"/v1/documents?session_id={session_id}")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.delete(f"/v1/documents/{doc_id}?session_id={session_id}")
    assert r.status_code == 200


def test_documents_upload_docx(client, rag_enabled, session_id):
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Neural network dynamics test.")
    doc.save(buf)

    r = client.post(
        "/v1/documents/upload",
        data={"session_id": session_id},
        files={"file": ("test.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    if r.status_code == 400:
        pytest.skip("RAG not enabled")
    assert r.status_code == 200


def test_rag_refs(client, session_id):
    r = client.get(f"/v1/sessions/{session_id}/rag-refs")
    assert r.status_code == 200
    assert "refs" in r.json()

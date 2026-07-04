# =============================================================================
# 文档 ingestion API — L3 RAG 向量记忆（按 session_id 隔离）。
#
# 端点：
#     POST   /v1/documents           — 上传/索引文档到指定会话
#     GET    /v1/documents           — 列出某会话已索引文档（?session_id=）
#     DELETE /v1/documents           — purge=true 时清空全部 RAG 文档
#     DELETE /v1/documents/{doc_id}  — 删除文档及向量（?session_id=）
#     GET    /v1/sessions/{id}/rag-refs — 会话 RAG 引用（doc_id + snippet）
# =============================================================================

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from server.config import get_settings
from server.memory.rag.doc_ingest import extract_text_from_docx
from server.memory.rag.pdf_ingest import (
    build_literature_metadata,
    extract_text_from_pdf,
)
from server.memory.rag.session_refs import SessionRagRefStore
from server.memory.rag.store import get_rag_store, reset_rag_store
from shared.schemas import (
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    SessionRagRef,
    SessionRagRefsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


def _to_info(record) -> DocumentInfo:
    """将 RagStore 的 DocumentRecord 转为 API 用的 DocumentInfo。"""
    return DocumentInfo(
        doc_id=record.doc_id,
        session_id=record.session_id,
        title=record.title,
        source=record.source,
        chunk_count=record.chunk_count,
        created_at=record.created_at,
    )


@router.post("/v1/documents", response_model=DocumentUploadResponse)
async def upload_document(request: DocumentUploadRequest) -> DocumentUploadResponse:
    """
    上传文档正文并写入指定会话的 Chroma 向量库。

    参数:
        request: 含 session_id、content、title、source、可选 doc_id

    返回:
        DocumentUploadResponse，含索引后的 document 元数据
    """
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    try:
        record = get_rag_store().add_document(
            request.content,
            session_id=request.session_id,
            title=request.title,
            source=request.source,
            doc_id=request.doc_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("文档索引失败")
        raise HTTPException(status_code=500, detail=f"索引失败: {exc}") from exc

    return DocumentUploadResponse(document=_to_info(record))


@router.post("/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    arxiv_id: str | None = Form(default=None),
) -> DocumentUploadResponse:
    """上传 PDF 文件并解析入库。"""
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")
    if not settings.pdf_ingest_enabled:
        raise HTTPException(status_code=400, detail="PDF 入库未启用")

    data = await file.read()
    filename = file.filename or "upload"
    lower = filename.lower()

    if lower.endswith(".pdf"):
        try:
            content = extract_text_from_pdf(data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {exc}") from exc
        source = f"pdf:{filename}"
    elif lower.endswith(".docx"):
        try:
            content = extract_text_from_docx(data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"DOCX 解析失败: {exc}") from exc
        source = f"docx:{filename}"
    elif lower.endswith((".md", ".txt", ".markdown")):
        content = data.decode("utf-8", errors="replace")
        source = f"file:{filename}"
    else:
        raise HTTPException(
            status_code=400,
            detail="不支持的文件类型，请上传 .pdf、.docx、.md 或 .txt",
        )

    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    _meta = build_literature_metadata(arxiv_id=arxiv_id)
    source = f"{source}|meta:{arxiv_id or ''}"
    try:
        record = get_rag_store().add_document(
            content,
            session_id=session_id,
            title=title or filename,
            source=source,
        )
    except Exception as exc:
        logger.exception("文档索引失败")
        raise HTTPException(status_code=500, detail=f"索引失败: {exc}") from exc

    return DocumentUploadResponse(document=_to_info(record))


@router.post("/v1/documents/from-arxiv", response_model=DocumentUploadResponse)
async def ingest_from_arxiv(
    session_id: str = Query(..., min_length=1),
    arxiv_id: str = Query(..., min_length=1, description="如 2301.00001"),
    title: str | None = Query(default=None),
) -> DocumentUploadResponse:
    """从 arXiv 下载 PDF 并入库。"""
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用")
    if not settings.pdf_ingest_enabled:
        raise HTTPException(status_code=400, detail="PDF 入库未启用")

    aid = arxiv_id.strip().replace("arXiv:", "")
    pdf_url = f"https://arxiv.org/pdf/{aid}.pdf"
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
            content = extract_text_from_pdf(resp.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"arXiv 下载失败: {exc}") from exc

    if not content.strip():
        raise HTTPException(status_code=400, detail="PDF 无文本内容")

    _meta = build_literature_metadata(arxiv_id=aid, relation_to_project="arxiv ingest")
    record = get_rag_store().add_document(
        content,
        session_id=session_id,
        title=title or f"arXiv:{aid}",
        source=f"{pdf_url}|meta:{aid}",
        doc_id=f"arxiv-{aid}",
    )
    return DocumentUploadResponse(document=_to_info(record))


@router.get("/v1/documents", response_model=DocumentListResponse)
async def list_documents(
    session_id: str = Query(..., min_length=1, description="会话 ID"),
) -> DocumentListResponse:
    """
    列出指定会话已索引的 RAG 文档（ENABLE_RAG=false 时返回空列表）。
    """
    settings = get_settings()
    if not settings.enable_rag:
        return DocumentListResponse(documents=[], total=0)

    records = get_rag_store().list_documents(session_id)
    docs = [_to_info(r) for r in records]
    return DocumentListResponse(documents=docs, total=len(docs))


@router.delete("/v1/documents")
async def purge_all_documents(
    purge: bool = Query(
        False,
        description="purge=true 时清空全部 RAG 文档与向量",
    ),
) -> dict[str, str | int]:
    """清空全部 RAG 文档（需 purge=true，跨会话）。"""
    if not purge:
        raise HTTPException(
            status_code=400,
            detail="请使用 ?purge=true 确认清空全部 RAG 文档",
        )

    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    deleted = get_rag_store().clear_all_documents()
    reset_rag_store()
    return {"status": "cleared", "deleted": deleted}


@router.delete("/v1/documents/session/{session_id}")
async def clear_session_documents(session_id: str) -> dict[str, str | int]:
    """清空指定会话的全部 RAG 文档。"""
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    deleted = get_rag_store().clear_session_documents(session_id)
    try:
        SessionRagRefStore(settings.session_db_path).clear_session(session_id)
    except Exception:
        logger.exception("清除会话 RAG 引用失败 session_id=%s", session_id)
    return {"status": "cleared", "session_id": session_id, "deleted": deleted}


@router.delete("/v1/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    session_id: str = Query(..., min_length=1, description="会话 ID"),
) -> dict[str, str]:
    """删除指定会话内的文档及其向量 chunk。"""
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    deleted = get_rag_store().delete_document(doc_id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    return {"status": "deleted", "doc_id": doc_id, "session_id": session_id}


@router.get("/v1/sessions/{session_id}/rag-refs", response_model=SessionRagRefsResponse)
async def get_session_rag_refs(session_id: str) -> SessionRagRefsResponse:
    """查询某会话检索过的 RAG 文档引用（doc_id + 片段预览）。"""
    settings = get_settings()
    store = SessionRagRefStore(settings.session_db_path)
    refs = [
        SessionRagRef(
            doc_id=ref["doc_id"],
            snippet=ref["snippet"],
            created_at=ref.get("created_at"),
        )
        for ref in store.get_refs(session_id)
    ]
    return SessionRagRefsResponse(session_id=session_id, refs=refs)

# =============================================================================
# 文档 ingestion API — L3 RAG 向量记忆。
#
# 端点：
#     POST   /v1/documents           — 上传/索引文档
#     GET    /v1/documents           — 列出已索引文档
#     DELETE /v1/documents/{doc_id}  — 删除文档及向量
#     GET    /v1/sessions/{id}/rag-refs — 会话 RAG 引用（doc_id + snippet）
# =============================================================================

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from server.config import get_settings
from server.memory.rag.session_refs import SessionRagRefStore
from server.memory.rag.store import get_rag_store
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
        title=record.title,
        source=record.source,
        chunk_count=record.chunk_count,
        created_at=record.created_at,
    )


@router.post("/v1/documents", response_model=DocumentUploadResponse)
async def upload_document(request: DocumentUploadRequest) -> DocumentUploadResponse:
    """
    上传文档正文并写入 Chroma 向量库。

    参数:
        request: 含 content、title、source、可选 doc_id

    返回:
        DocumentUploadResponse，含索引后的 document 元数据

    异常:
        HTTPException 400: RAG 未启用或内容无效
        HTTPException 500: 索引过程失败
    """
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    try:
        record = get_rag_store().add_document(
            request.content,
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


@router.get("/v1/documents", response_model=DocumentListResponse)
async def list_documents() -> DocumentListResponse:
    """
    列出已索引的 RAG 文档（ENABLE_RAG=false 时返回空列表）。

    返回:
        DocumentListResponse: documents 与 total
    """
    settings = get_settings()
    if not settings.enable_rag:
        return DocumentListResponse(documents=[], total=0)

    records = get_rag_store().list_documents()
    docs = [_to_info(r) for r in records]
    return DocumentListResponse(documents=docs, total=len(docs))


@router.delete("/v1/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, str]:
    """
    删除指定文档及其向量 chunk。

    参数:
        doc_id: 文档唯一 ID

    返回:
        status=deleted 与 doc_id

    异常:
        HTTPException 400/404: RAG 未启用或文档不存在
    """
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    deleted = get_rag_store().delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/v1/sessions/{session_id}/rag-refs", response_model=SessionRagRefsResponse)
async def get_session_rag_refs(session_id: str) -> SessionRagRefsResponse:
    """
    查询某会话检索过的 RAG 文档引用（doc_id + 片段预览）。

    参数:
        session_id: 会话 ID

    返回:
        SessionRagRefsResponse
    """
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

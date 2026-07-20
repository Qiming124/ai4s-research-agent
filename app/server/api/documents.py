# =============================================================================
# 文档 ingestion API — L3 RAG 向量记忆（按 session_id 隔离）。
#
# 职责：
#     1. 上传 PDF/DOCX/文本并切块嵌入到 Chroma 向量库
#     2. 列出、删除会话文档；支持 purge 清空
#     3. 暴露会话 RAG 引用（doc_id + snippet）供前端展示
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/rag/store.py、pdf_ingest.py、doc_ingest.py、session_refs.py
#
# 阅读提示：
#     - 新人先看 upload_document 与 list_documents
#     - 向量隔离逻辑在 rag/store.py 的 project namespace
#
# 端点：
#     POST   /v1/documents           — 上传/索引文档到指定会话
#     GET    /v1/documents           — 列出某会话已索引文档（?session_id=）
#     DELETE /v1/documents           — purge=true 时清空全部 RAG 文档
#     DELETE /v1/documents/{doc_id}  — 删除文档及向量（?session_id=）
#     GET    /v1/sessions/{id}/rag-refs — 会话 RAG 引用（doc_id + snippet）
#
# Debug：
#     - 上传 403 → ENABLE_RAG=false
#     - 检索无结果 → embedding 模型或 chunk 为空
#     - PDF 解析失败 → 检查 pdf_ingest 日志与文件编码
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
        project_id=getattr(record, "project_id", "default") or "default",
        title=record.title,
        source=record.source,
        chunk_count=record.chunk_count,
        created_at=record.created_at,
    )


@router.post("/v1/documents", response_model=DocumentUploadResponse, summary="文本入库 RAG")
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
            project_id=request.project_id,
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


@router.post("/v1/documents/upload", response_model=DocumentUploadResponse, summary="上传 PDF/DOCX/MD 文件入库")
async def upload_document_file(
    session_id: str = Form(..., description="上传所属会话 ID", examples=["sess_demo"]),
    file: UploadFile = File(..., description="PDF / DOCX / MD / TXT 文件"),
    title: str | None = Form(default=None, description="文档标题；省略则用文件名", examples=["Loss Landscape Notes"]),
    arxiv_id: str | None = Form(default=None, description="可选 arXiv ID，写入文献元数据", examples=["1412.0233"]),
    project_id: str | None = Form(default=None, description="课题 ID；缺省由会话反查", examples=["default"]),
) -> DocumentUploadResponse:
    """上传 PDF/DOCX/MD/TXT 文件并解析入库到课题共享 RAG。"""
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
            project_id=project_id,
            title=title or filename,
            source=source,
        )
    except Exception as exc:
        logger.exception("文档索引失败")
        raise HTTPException(status_code=500, detail=f"索引失败: {exc}") from exc

    return DocumentUploadResponse(document=_to_info(record))


@router.post("/v1/documents/from-arxiv", response_model=DocumentUploadResponse, summary="从 arXiv 导入 PDF")
async def ingest_from_arxiv(
    session_id: str = Query(..., min_length=1, description="会话 ID", examples=["sess_demo"]),
    arxiv_id: str = Query(..., min_length=1, description="arXiv ID，如 1412.0233", examples=["1412.0233"]),
    title: str | None = Query(default=None, description="可选标题覆盖", examples=["The Loss Surfaces of Multilayer Networks"]),
    project_id: str | None = Query(default=None, description="课题 ID", examples=["default"]),
) -> DocumentUploadResponse:
    """从 arXiv 下载 PDF 并解析入库。"""
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
        project_id=project_id,
        title=title or f"arXiv:{aid}",
        source=f"{pdf_url}|meta:{aid}",
        doc_id=f"arxiv-{aid}",
    )
    return DocumentUploadResponse(document=_to_info(record))


@router.get("/v1/documents", response_model=DocumentListResponse, summary="列出 RAG 文档")
async def list_documents(
    session_id: str | None = Query(None, description="会话 ID（用于反查课题）", examples=["sess_demo"]),
    project_id: str | None = Query(None, description="课题 ID", examples=["default"]),
) -> DocumentListResponse:
    """
    列出指定课题已索引的 RAG 文档（ENABLE_RAG=false 时返回空列表）。
    """
    settings = get_settings()
    if not settings.enable_rag:
        return DocumentListResponse(documents=[], total=0)
    if not session_id and not project_id:
        raise HTTPException(status_code=400, detail="需要 session_id 或 project_id")

    records = get_rag_store().list_documents(session_id=session_id, project_id=project_id)
    docs = [_to_info(r) for r in records]
    return DocumentListResponse(documents=docs, total=len(docs))


@router.delete("/v1/documents", summary="清空全部 RAG 文档")
async def purge_all_documents(
    purge: bool = Query(
        False,
        description="purge=true 时清空全部 RAG 文档与向量",
        examples=[True],
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


@router.delete("/v1/documents/session/{session_id}", summary="清空会话 RAG 文档")
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


@router.delete("/v1/documents/{doc_id}", summary="删除单条 RAG 文档")
async def delete_document(
    doc_id: str,
    session_id: str = Query(..., min_length=1, description="会话 ID", examples=["sess_demo"]),
) -> dict[str, str]:
    """删除指定会话内的文档及其向量 chunk。"""
    settings = get_settings()
    if not settings.enable_rag:
        raise HTTPException(status_code=400, detail="RAG 未启用（ENABLE_RAG=false）")

    deleted = get_rag_store().delete_document(doc_id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    return {"status": "deleted", "doc_id": doc_id, "session_id": session_id}


@router.get("/v1/sessions/{session_id}/rag-refs", response_model=SessionRagRefsResponse, summary="会话 RAG 引用")
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

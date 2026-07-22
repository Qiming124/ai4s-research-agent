# =============================================================================
# L4 结构化科研记忆 HTTP API。
#
# 职责：
#     1. CRUD 定理/引理/假设/结论等结构化条目
#     2. 管理记忆图谱边（depends_on / contradicts）
#     3. 按 session_id / kind 过滤列表
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/memory/structured/store.py
#
# 图谱边 API 仍保留（POST/DELETE edges）；已移除 GET /graph 视图。
# 阅读提示：
#     - 新人先看 list_structured_memory 与 create_structured_memory
#     - 边见 create_memory_edge
#
# Debug：
#     - 条目未出现在 prompt → injection.py 未启用或 session 过滤
#     - 边创建失败 → 源/目标 entry_id 不存在
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Path, Query, UploadFile

from server.memory.structured.store import get_structured_memory_store
from shared.schemas import (
    MemoryEdge,
    MemoryEdgeCreateRequest,
    StructuredMemoryCreateRequest,
    StructuredMemoryEntry,
    StructuredMemoryImportCandidate,
    StructuredMemoryImportPreviewResponse,
    StructuredMemoryListResponse,
    StructuredMemoryMarkdownPreviewRequest,
    StructuredMemoryUpdateRequest,
)

router = APIRouter(tags=["memory"])


@router.get(
    "/v1/memory/structured",
    response_model=StructuredMemoryListResponse,
    summary="结构化记忆列表",
)
async def list_structured_memory(
    session_id: str | None = Query(
        default=None,
        description="按会话过滤",
        examples=["sess_demo"],
    ),
    kind: str | None = Query(
        default=None,
        description="按类型过滤：theorem/hypothesis/conclusion/citation/note",
        examples=["theorem"],
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="返回条数上限",
        examples=[50],
    ),
) -> StructuredMemoryListResponse:
    """按会话/类型列出 L4 结构化记忆条目。"""
    store = get_structured_memory_store()
    entries = store.list_entries(session_id=session_id, kind=kind, limit=limit)
    return StructuredMemoryListResponse(
        entries=[StructuredMemoryEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get(
    "/v1/memory/structured/global",
    response_model=StructuredMemoryListResponse,
    summary="全局结构化记忆",
)
async def list_global_structured_memory(
    kind: str | None = Query(
        default=None,
        description="按类型过滤",
        examples=["theorem"],
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="返回条数上限",
        examples=[50],
    ),
) -> StructuredMemoryListResponse:
    """仅列出全局（非会话绑定）结构化记忆。"""
    store = get_structured_memory_store()
    entries = store.list_entries(global_only=True, kind=kind, limit=limit)
    return StructuredMemoryListResponse(
        entries=[StructuredMemoryEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get(
    "/v1/memory/structured/{entry_id}/versions",
    summary="记忆条目版本列表",
)
async def list_entry_versions(
    entry_id: int = Path(..., description="记忆条目 ID", examples=[1]),
) -> dict:
    """列出某条目的 L4 历史版本。"""
    from server.memory.projects import get_project_store

    store = get_project_store()
    versions = store.list_entry_versions(entry_id)
    return {"entry_id": entry_id, "versions": versions, "total": len(versions)}


@router.post(
    "/v1/memory/structured/{entry_id}/versions",
    summary="新建记忆条目版本",
)
async def create_entry_version(
    entry_id: int = Path(..., description="记忆条目 ID", examples=[1]),
) -> dict:
    """基于当前条目内容快照新建一个版本。"""
    from server.memory.projects import get_project_store

    memory = get_structured_memory_store()
    entries = memory.list_entries(limit=500)
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    meta = entry.get("metadata") or {}
    version = get_project_store().save_entry_version(
        entry_id,
        entry["title"],
        entry["body"],
        meta,
        status=str(meta.get("status", "draft")),
    )
    return version


@router.post(
    "/v1/memory/structured/preview-markdown",
    response_model=StructuredMemoryImportPreviewResponse,
    summary="Markdown 导入预览",
)
async def preview_markdown_import(
    request: StructuredMemoryMarkdownPreviewRequest,
) -> StructuredMemoryImportPreviewResponse:
    """按 ## 定理/引理 规则解析候选，不写库。"""
    from server.memory.structured.import_extract import candidates_from_markdown

    candidates = candidates_from_markdown(request.content)
    return StructuredMemoryImportPreviewResponse(
        filename="",
        text_chars=len(request.content),
        truncated=False,
        candidates=[StructuredMemoryImportCandidate.model_validate(c) for c in candidates],
        warnings=[] if candidates else ["未识别到 ## 定理/引理/推论 标题"],
    )


@router.post(
    "/v1/memory/structured/import-preview",
    response_model=StructuredMemoryImportPreviewResponse,
    summary="PDF/文档导入预览",
)
async def import_file_preview(
    file: UploadFile = File(..., description="PDF / DOCX / MD / TXT"),
    session_id: str | None = Form(default=None, description="可选会话 ID（仅记录用）"),
) -> StructuredMemoryImportPreviewResponse:
    """抽取全文并由 LLM 生成定理候选；确认入库由前端 POST 条目完成。"""
    from server.memory.rag.doc_ingest import extract_text_from_docx
    from server.memory.rag.pdf_ingest import extract_text_from_pdf
    from server.memory.structured.import_extract import (
        candidates_from_markdown,
        extract_candidates_with_llm,
    )

    _ = session_id  # 预留：后续可按会话限流/审计
    filename = file.filename or "upload.bin"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")

    lower = filename.lower()
    warnings: list[str] = []
    try:
        if lower.endswith(".pdf"):
            text = extract_text_from_pdf(data)
        elif lower.endswith(".docx"):
            text = extract_text_from_docx(data)
        elif lower.endswith((".md", ".txt", ".markdown")):
            text = data.decode("utf-8", errors="replace")
        else:
            raise HTTPException(
                status_code=400,
                detail="仅支持 .pdf / .docx / .md / .txt",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"解析失败: {exc}") from exc

    text = (text or "").strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="未能抽取到可选文字（扫描版 PDF 暂不支持 OCR）",
        )

    truncated = False
    # 仅在极端体积时做基础设施保护（约 2M 字符），不为省 token
    hard_cap = 2_000_000
    if len(text) > hard_cap:
        text = text[:hard_cap]
        truncated = True
        warnings.append(f"正文超过 {hard_cap} 字符，已截断尾部")

    candidates: list[dict] = []
    if lower.endswith((".md", ".markdown", ".txt")) and (
        "## 定理" in text or "## 引理" in text or "## Theorem" in text or "## Lemma" in text
    ):
        candidates = candidates_from_markdown(text)
        if not candidates:
            warnings.append("Markdown 标题规则未命中，改用 LLM 抽取")

    if not candidates:
        try:
            candidates = await extract_candidates_with_llm(text)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM 抽取失败: {exc}") from exc

    if not candidates:
        warnings.append("未抽到候选条目，可改用 Markdown 手工整理后导入")

    return StructuredMemoryImportPreviewResponse(
        filename=filename,
        text_chars=len(text),
        truncated=truncated,
        candidates=[StructuredMemoryImportCandidate.model_validate(c) for c in candidates],
        warnings=warnings,
    )


@router.post(
    "/v1/memory/structured",
    response_model=StructuredMemoryEntry,
    summary="写入结构化记忆",
)
async def create_structured_memory(
    request: StructuredMemoryCreateRequest,
) -> StructuredMemoryEntry:
    """新建一条定理/假设/结论等结构化记忆。"""
    store = get_structured_memory_store()
    meta = dict(request.metadata or {})
    if "source" not in meta:
        meta["source"] = "manual"
    if "status" not in meta:
        meta["status"] = "draft"
    entry = store.create_entry(
        session_id=request.session_id,
        kind=request.kind,
        title=request.title,
        body=request.body,
        metadata=meta,
    )
    return StructuredMemoryEntry.model_validate(entry)


@router.patch(
    "/v1/memory/structured/{entry_id}",
    response_model=StructuredMemoryEntry,
    summary="更新结构化记忆",
)
async def update_structured_memory(
    request: StructuredMemoryUpdateRequest,
    entry_id: int = Path(..., description="记忆条目 ID", examples=[1]),
) -> StructuredMemoryEntry:
    if (
        request.kind is None
        and request.title is None
        and request.body is None
        and request.metadata is None
    ):
        raise HTTPException(status_code=400, detail="至少提供一个更新字段")
    store = get_structured_memory_store()
    entry = store.update_entry(
        entry_id,
        kind=request.kind,
        title=request.title,
        body=request.body,
        metadata=request.metadata,
    )
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    return StructuredMemoryEntry.model_validate(entry)


@router.delete(
    "/v1/memory/structured/{entry_id}",
    summary="删除结构化记忆",
)
async def delete_structured_memory(
    entry_id: int = Path(..., description="记忆条目 ID", examples=[1]),
) -> dict:
    store = get_structured_memory_store()
    ok = store.delete_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"ok": True, "id": entry_id}


@router.post(
    "/v1/memory/structured/{entry_id}/edges",
    response_model=MemoryEdge,
    summary="创建知识图谱边",
)
async def create_memory_edge(
    request: MemoryEdgeCreateRequest,
    entry_id: int = Path(..., description="起点条目 ID", examples=[1]),
) -> MemoryEdge:
    """从 entry_id 指向 to_id，创建 depends_on/contradicts/supports/cites 边。"""
    store = get_structured_memory_store()
    try:
        edge = store.create_edge(
            from_id=entry_id,
            to_id=request.to_id,
            relation=request.relation,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MemoryEdge.model_validate(edge)

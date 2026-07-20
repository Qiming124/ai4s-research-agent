# =============================================================================
# 论文导出 HTTP API（LaTeX / Markdown / DOCX / PDF）。
#
# 职责：
#     1. 预览与导出结构化记忆、参考文献、工作区内容
#     2. 调用 builder 聚合条目，再经 docx_exporter / pdf_exporter 生成二进制
#     3. 可选 AI 润色导出 Markdown
#
# 架构位置：
#     - 被调用：server/main.py include_router
#     - 调用：server/export/builder.py、docx_exporter.py、pdf_exporter.py、ai_polish.py
#
# 阅读提示：
#     - 新人先看 export_preview 与 export_latex / export_docx / export_pdf
#     - 数据来源见 builder.collect_export_entries()
#
# Debug：
#     - PDF 乱码 → pdf_fonts 中文字体未就绪
#     - DOCX 公式空白 → math_docx_prep 预处理或 pandoc 未安装
#     - 导出为空 → session_id 无 L4 结构化记忆条目
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from server.export.ai_polish import polish_export_markdown
from server.export.builder import (
    build_latex_document,
    build_markdown_document,
    collect_export_entries,
    describe_export_sources,
)
from server.export.docx_exporter import build_docx_bytes
from server.export.pdf_exporter import build_pdf_bytes
from shared.schemas import (
    ExportPolishResponse,
    ExportPreviewResponse,
    LatexExportRequest,
    LatexExportResponse,
)

router = APIRouter(tags=["export"])


async def _resolve_export_payload(request: LatexExportRequest) -> tuple[list, str, bool]:
    entries = collect_export_entries(
        session_id=request.session_id,
        include_global=request.include_global,
        include_chat=request.include_chat,
    )
    markdown = build_markdown_document(title=request.title, entries=entries)
    ai_applied = False
    if request.use_ai and (request.ai_instructions or "").strip():
        markdown, ai_applied = await polish_export_markdown(
            title=request.title,
            markdown=markdown,
            instructions=request.ai_instructions or "",
        )
    return entries, markdown, ai_applied


@router.get(
    "/v1/export/preview",
    response_model=ExportPreviewResponse,
    summary="导出预览统计",
)
async def export_preview(
    session_id: str | None = Query(
        default=None,
        description="会话 ID；省略则仅统计全局等来源",
        examples=["sess_demo"],
    ),
    include_global: bool = Query(
        default=True,
        description="是否计入全局结构化记忆",
        examples=[True],
    ),
    include_chat: bool = Query(
        default=True,
        description="是否计入会话对话",
        examples=[True],
    ),
) -> ExportPreviewResponse:
    """返回可导出条目数量与来源提示（不生成文件）。"""
    info = describe_export_sources(
        session_id=session_id,
        include_global=include_global,
        include_chat=include_chat,
    )
    return ExportPreviewResponse(**info)


@router.post(
    "/v1/export/polish",
    response_model=ExportPolishResponse,
    summary="AI 润色导出草稿",
)
async def export_polish_preview(request: LatexExportRequest) -> ExportPolishResponse:
    """预览 AI 润色后的 Markdown（不下载文件）。须填写 ai_instructions。"""
    if not (request.ai_instructions or "").strip():
        raise HTTPException(status_code=400, detail="请填写 AI 润色要求")
    _, markdown, ai_applied = await _resolve_export_payload(
        request.model_copy(update={"use_ai": True}),
    )
    return ExportPolishResponse(
        markdown=markdown,
        ai_applied=ai_applied,
        message="AI 润色已应用" if ai_applied else "AI 润色未生效，已返回原稿",
    )


@router.post(
    "/v1/export/latex",
    response_model=LatexExportResponse,
    summary="导出 LaTeX",
)
async def export_latex(request: LatexExportRequest) -> LatexExportResponse:
    """聚合记忆与对话，生成 LaTeX 源码（可落盘并附 .bib）。"""
    entries = collect_export_entries(
        session_id=request.session_id,
        include_global=request.include_global,
        include_chat=request.include_chat,
    )
    latex, export_file, bib_path = build_latex_document(
        title=request.title,
        entries=entries,
        project_id=request.project_id,
    )
    return LatexExportResponse(latex=latex, path=str(export_file), bib_path=bib_path)


@router.post("/v1/export/md", summary="导出 Markdown 文件")
async def export_markdown(request: LatexExportRequest) -> Response:
    """下载 Markdown 附件（可选 AI 润色）。"""
    _, markdown, _ = await _resolve_export_payload(request)
    filename = _safe_filename(request.title, "md")
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers=_download_headers(filename),
    )


@router.post("/v1/export/docx", summary="导出 Word DOCX")
async def export_docx(request: LatexExportRequest) -> Response:
    """下载 DOCX 附件；需 pandoc 等依赖，否则 503。"""
    _, markdown, _ = await _resolve_export_payload(request)
    try:
        data = build_docx_bytes(markdown=markdown)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = _safe_filename(request.title, "docx")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=_download_headers(filename),
    )


@router.post("/v1/export/pdf", summary="导出 PDF")
async def export_pdf(request: LatexExportRequest) -> Response:
    """下载 PDF 附件；中文字体缺失时可能失败。"""
    entries, markdown, _ = await _resolve_export_payload(request)
    try:
        data = build_pdf_bytes(markdown=markdown, entries=entries)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF 导出失败: {exc}") from exc

    filename = _safe_filename(request.title, "pdf")
    return Response(
        content=data,
        media_type="application/pdf",
        headers=_download_headers(filename),
    )


def _download_headers(filename: str) -> dict[str, str]:
    from urllib.parse import quote

    ascii_name = filename.encode("ascii", "ignore").decode() or f"export.{filename.rsplit('.', 1)[-1]}"
    return {
        "Content-Disposition": (
            f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
        ),
    }


def _safe_filename(title: str, ext: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (title or "export"))
    safe = safe.strip("_") or "export"
    return f"{safe[:60]}.{ext}"

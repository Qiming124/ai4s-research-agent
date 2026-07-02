# PDF 解析与入库。

from __future__ import annotations

import io
import re
from typing import Any


def extract_text_from_pdf(data: bytes) -> str:
    """从 PDF 字节提取纯文本。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf 未安装。请执行: pip install pypdf 或 pip install -e '.[pdf]'") from exc

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            parts.append(f"<!-- page {i + 1} -->\n{text}")
    return "\n\n".join(parts)


def chunk_pdf_text(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[dict[str, Any]]:
    """按段落切块并附带页码元数据。"""
    from server.memory.rag.chunking import chunk_text

    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    result: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        page_match = re.search(r"page (\d+)", chunk)
        page = int(page_match.group(1)) if page_match else None
        result.append({"text": chunk, "section": f"chunk_{i}", "page": page})
    return result


def build_literature_metadata(
    *,
    arxiv_id: str | None = None,
    loss_form: str = "",
    assumptions: list[str] | None = None,
    main_results: list[str] | None = None,
    relation_to_project: str = "",
) -> dict[str, Any]:
    """文献笔记 metadata 模板。"""
    return {
        "arxiv_id": arxiv_id,
        "loss_form": loss_form,
        "assumptions": assumptions or [],
        "main_results": main_results or [],
        "relation_to_project": relation_to_project,
    }

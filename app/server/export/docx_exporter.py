# DOCX 导出（Markdown → pandoc → DOCX，回退 python-docx）。

from __future__ import annotations

import io
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def build_docx_bytes(*, markdown: str) -> bytes:
    """从 Markdown 生成 DOCX。"""
    from server.export.pandoc_converter import convert_markdown_to_docx, pandoc_available

    if pandoc_available():
        try:
            return convert_markdown_to_docx(markdown)
        except RuntimeError as exc:
            logger.warning("pandoc Markdown→DOCX 失败，回退 python-docx: %s", exc)

    return _docx_from_markdown_fallback(markdown)


def build_docx_bytes_from_entries(*, title: str, entries: list[dict[str, Any]]) -> bytes:
    """兼容旧调用：先转 Markdown 再导出 DOCX。"""
    from server.export.builder import build_markdown_document

    return build_docx_bytes(markdown=build_markdown_document(title=title, entries=entries))


def _docx_from_markdown_fallback(markdown: str) -> bytes:
    try:
        from docx import Document
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        from docx.shared import Pt
    except ImportError as exc:
        raise RuntimeError(
            "python-docx 未安装。请执行: pip install python-docx 或 pip install -e '.[docx]'"
        ) from exc

    doc = Document()
    lines = markdown.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("# "):
            heading = doc.add_heading(line[2:].strip(), level=0)
            heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            idx += 1
            continue
        if line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
            idx += 1
            continue
        if not line.strip():
            idx += 1
            continue
        para_lines = [line]
        idx += 1
        while idx < len(lines) and lines[idx].strip() and not lines[idx].startswith("#"):
            para_lines.append(lines[idx])
            idx += 1
        p = doc.add_paragraph("\n".join(para_lines))
        p.style.font.size = Pt(11)

    if not doc.paragraphs:
        doc.add_paragraph(markdown or "（空文档）")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _kind_label(kind: str) -> str:
    labels = {
        "theorem": "定理",
        "lemma": "引理",
        "hypothesis": "假设",
        "note": "笔记",
        "definition": "定义",
    }
    return labels.get(kind, kind)

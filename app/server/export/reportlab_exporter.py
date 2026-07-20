# =============================================================================
# Reportlab PDF 导出（内置 CID 中文字体）。
#
# 职责：
#     1. build_reportlab_pdf_bytes() 从结构化 entries 直接排版 PDF
#     2. 使用 STSong-Light CID 字体，无需额外字体文件
#     3. 作为 pandoc 不可用时的最终回退路径
#
# 架构位置：
#     - 被调用：server/export/pdf_exporter.py（回退分支）
#     - 调用：reportlab 库
#
# 阅读提示：
#     - 新人先看 build_reportlab_pdf_bytes
#
# Debug：
#     - ImportError → pip install reportlab
#     - 英文正常中文缺字 → CID 字体字集限制，优先 pandoc 路径
# =============================================================================

from __future__ import annotations

import io
from typing import Any
from xml.sax.saxutils import escape

_KIND_LABELS = {
    "theorem": "定理",
    "lemma": "引理",
    "hypothesis": "假设",
    "note": "笔记",
    "definition": "定义",
    "conclusion": "结论",
}

_CID_FONT = "STSong-Light"


def build_reportlab_pdf_bytes(*, title: str, entries: list[dict[str, Any]]) -> bytes:
    try:
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError(
            "reportlab 未安装。请执行: pip install reportlab 或 pip install -e '.[export]'"
        ) from exc

    pdfmetrics.registerFont(UnicodeCIDFont(_CID_FONT))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=48,
        bottomMargin=48,
        title=title or "研究报告",
    )

    title_style = ParagraphStyle(
        "ExportTitle",
        fontName=_CID_FONT,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        "ExportHeading",
        fontName=_CID_FONT,
        fontSize=13,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ExportBody",
        fontName=_CID_FONT,
        fontSize=11,
        leading=16,
        spaceAfter=4,
    )

    story: list[Any] = [Paragraph(_para(title or "研究报告"), title_style), Spacer(1, 8)]

    if not entries:
        story.append(Paragraph(_para("（暂无定理/引理条目）"), body_style))
    else:
        for entry in entries:
            kind = entry.get("kind", "note")
            entry_title = entry.get("title", "") or "未命名"
            body = entry.get("body", "") or ""
            label = _KIND_LABELS.get(kind, kind)
            story.append(Paragraph(_para(f"{label}：{entry_title}"), heading_style))
            if body.strip():
                for line in body.split("\n"):
                    if line.strip():
                        story.append(Paragraph(_para(line), body_style))
            else:
                story.append(Spacer(1, 4))

    doc.build(story)
    return buf.getvalue()


def _para(text: str) -> str:
    """转义并保留基本换行。"""
    return escape(text).replace("\t", "    ")

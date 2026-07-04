# PDF 导出（Markdown 渲染 → HTML → PDF；Docker 可用 pandoc+xelatex）。

from __future__ import annotations

import logging
import re
from typing import Any

from server.export.html_pdf_renderer import build_pdf_from_markdown
from server.export.pandoc_converter import convert_markdown_to_pdf, pandoc_available
from server.export.pdf_fonts import resolve_cjk_font_path

logger = logging.getLogger(__name__)

_CJK_FONT_FAMILY = "NotoSansSC"


def build_pdf_bytes(
    *,
    markdown: str,
    entries: list[dict[str, Any]] | None = None,
) -> bytes:
    """从 Markdown 生成 PDF：先渲染 MD，再排版输出。"""
    title = _title_from_markdown(markdown)

    if pandoc_available() and _xelatex_available():
        try:
            return convert_markdown_to_pdf(markdown)
        except RuntimeError as exc:
            logger.warning("pandoc Markdown→PDF(xelatex) 失败，回退 HTML 渲染: %s", exc)

    try:
        return build_pdf_from_markdown(markdown, title=title)
    except RuntimeError as exc:
        logger.warning("HTML 渲染 PDF 失败，尝试结构化回退: %s", exc)

    fallback_entries = entries if entries is not None else _entries_from_markdown(markdown)
    return _unicode_text_pdf(title=title, entries=fallback_entries)


def build_pdf_bytes_from_entries(*, title: str, entries: list[dict[str, Any]]) -> bytes:
    """兼容旧调用：先转 Markdown 再导出 PDF。"""
    from server.export.builder import build_markdown_document

    md = build_markdown_document(title=title, entries=entries)
    return build_pdf_bytes(markdown=md, entries=entries)


def _xelatex_available() -> bool:
    import shutil

    return shutil.which("xelatex") is not None


def _title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or "研究报告"
    return "研究报告"


def _entries_from_markdown(markdown: str) -> list[dict[str, Any]]:
    """将简单 Markdown 解析为 fpdf2 可用的条目列表。"""
    entries: list[dict[str, Any]] = []
    heading_re = re.compile(r"^##\s*(定理|引理|假设|笔记|定义|结论)[：:]\s*(.+)$")
    kind_map = {
        "定理": "theorem",
        "引理": "lemma",
        "假设": "hypothesis",
        "笔记": "note",
        "定义": "definition",
        "结论": "conclusion",
    }
    current: dict[str, Any] | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current, body_lines
        if current is not None:
            current["body"] = "\n".join(body_lines).strip()
            entries.append(current)
        current = None
        body_lines = []

    for line in markdown.splitlines():
        if line.startswith("# "):
            continue
        m = heading_re.match(line.strip())
        if m:
            flush()
            label, entry_title = m.group(1), m.group(2).strip()
            current = {
                "kind": kind_map.get(label, "note"),
                "title": entry_title or "未命名",
                "body": "",
            }
            continue
        if current is not None:
            body_lines.append(line)

    flush()
    if not entries and markdown.strip():
        entries.append({"kind": "note", "title": "正文", "body": markdown.strip()})
    return entries


def _unicode_text_pdf(*, title: str, entries: list[dict]) -> bytes:
    """最终回退：fpdf2 + CJK 字体。"""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError(
            "无法生成 PDF：请安装 pandoc + texlive-xetex，或 pip install reportlab fpdf2"
        ) from exc

    font_path = resolve_cjk_font_path()
    if not font_path:
        raise RuntimeError(
            "无法生成中文 PDF：缺少中文字体。"
            " 请安装 fonts-noto-cjk / texlive-xetex，"
            " 或确保 app/server/export/fonts/ 下有 Noto 字体。"
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    w = pdf.epw

    pdf.add_font(_CJK_FONT_FAMILY, "", str(font_path))
    pdf.set_font(_CJK_FONT_FAMILY, size=16)
    pdf.multi_cell(w, 10, title or "研究报告")
    pdf.ln(4)
    pdf.set_font(_CJK_FONT_FAMILY, size=11)

    if not entries:
        pdf.multi_cell(w, 8, "（暂无定理/引理条目）")
    else:
        labels = {
            "theorem": "定理",
            "lemma": "引理",
            "hypothesis": "假设",
            "note": "笔记",
            "definition": "定义",
            "conclusion": "结论",
        }
        for entry in entries:
            kind = entry.get("kind", "note")
            entry_title = entry.get("title", "") or "未命名"
            body = entry.get("body", "") or ""
            label = labels.get(kind, kind)
            pdf.set_font(_CJK_FONT_FAMILY, size=12)
            pdf.multi_cell(w, 8, f"{label}：{entry_title}")
            pdf.set_font(_CJK_FONT_FAMILY, size=11)
            for line in body.split("\n"):
                chunk = line[:800]
                if chunk.strip():
                    pdf.multi_cell(w, 6, chunk)
            pdf.ln(2)

    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1")


_simple_text_pdf = _unicode_text_pdf

# 将渲染后的 HTML 转为 PDF（reportlab）。
# 支持标题/段落/列表/表格/代码块，以及 pandoc 数学 HTML（span.math / sub / sup）。

from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import Any
from xml.sax.saxutils import escape

_CID_FONT = "STSong-Light"


def build_pdf_from_html(html: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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
    )

    styles = {
        "h1": ParagraphStyle(
            "H1", fontName=_CID_FONT, fontSize=20, leading=26, alignment=TA_CENTER, spaceAfter=14
        ),
        "h2": ParagraphStyle(
            "H2", fontName=_CID_FONT, fontSize=14, leading=20, spaceBefore=12, spaceAfter=6
        ),
        "h3": ParagraphStyle(
            "H3", fontName=_CID_FONT, fontSize=12, leading=18, spaceBefore=8, spaceAfter=4
        ),
        "p": ParagraphStyle(
            "Body", fontName=_CID_FONT, fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=6
        ),
        "li": ParagraphStyle("ListItem", fontName=_CID_FONT, fontSize=11, leading=16, leftIndent=12),
        "code": ParagraphStyle(
            "Code",
            fontName=_CID_FONT,
            fontSize=9,
            leading=13,
            leftIndent=8,
            rightIndent=8,
            spaceAfter=6,
        ),
        "cell": ParagraphStyle(
            "Cell", fontName=_CID_FONT, fontSize=9, leading=13, alignment=TA_LEFT
        ),
        "cell_header": ParagraphStyle(
            "CellHeader", fontName=_CID_FONT, fontSize=9, leading=13, alignment=TA_LEFT
        ),
    }

    blocks = _HtmlBlockParser().parse(html)
    story: list[Any] = []
    usable_width = A4[0] - 96

    for block in blocks:
        kind = block["type"]
        text = block.get("text", "")
        if kind == "h1":
            story.append(Paragraph(_para_html(text), styles["h1"]))
        elif kind == "h2":
            story.append(Paragraph(_para_html(text), styles["h2"]))
        elif kind == "h3":
            story.append(Paragraph(_para_html(text), styles["h3"]))
        elif kind == "p":
            story.append(Paragraph(_para_html(text), styles["p"]))
        elif kind == "ul":
            for item in block.get("items", []):
                story.append(Paragraph(f"• {_para_html(item)}", styles["li"]))
            story.append(Spacer(1, 4))
        elif kind == "ol":
            for n, item in enumerate(block.get("items", []), start=1):
                story.append(Paragraph(f"{n}. {_para_html(item)}", styles["li"]))
            story.append(Spacer(1, 4))
        elif kind == "pre":
            # 保留换行：reportlab Paragraph 用 <br/>
            pre_text = _para_html(text).replace("\n", "<br/>")
            story.append(Paragraph(pre_text, styles["code"]))
        elif kind == "table":
            rows = block.get("rows") or []
            if not rows:
                continue
            col_count = max((len(r) for r in rows), default=1)
            col_w = usable_width / max(col_count, 1)
            data: list[list[Any]] = []
            for r_i, row in enumerate(rows):
                cells: list[Any] = []
                style_name = "cell_header" if r_i == 0 and block.get("has_header") else "cell"
                for c_i in range(col_count):
                    cell = row[c_i] if c_i < len(row) else ""
                    cells.append(Paragraph(_para_html(cell) or " ", styles[style_name]))
                data.append(cells)
            table = Table(data, colWidths=[col_w] * col_count, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), _CID_FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.7, 0.7, 0.7)),
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.Color(0.94, 0.94, 0.96),
                        ),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.Color(0.55, 0.55, 0.55)),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 6 * mm / 2))
        elif kind == "hr":
            story.append(Spacer(1, 8))

    if not story:
        story.append(Paragraph(_para_html("（空文档）"), styles["p"]))

    doc.build(story)
    return buf.getvalue()


def build_pdf_from_markdown(markdown: str, *, title: str | None = None) -> bytes:
    from server.export.pandoc_converter import convert_markdown_to_html

    html = convert_markdown_to_html(markdown, title=title)
    return build_pdf_from_html(html)


def _para_html(text: str) -> str:
    """将简易内联 HTML 转为 reportlab Paragraph 可用标记。"""
    text = _normalize_math_markup(text)
    placeholders = {
        "<strong>": "\x00B1\x00",
        "</strong>": "\x00B2\x00",
        "<b>": "\x00B1\x00",
        "</b>": "\x00B2\x00",
        "<em>": "\x00I1\x00",
        "</em>": "\x00I2\x00",
        "<i>": "\x00I1\x00",
        "</i>": "\x00I2\x00",
        "<code>": "\x00C1\x00",
        "</code>": "\x00C2\x00",
        "<super>": "\x00U1\x00",
        "</super>": "\x00U2\x00",
        "<sub>": "\x00S1\x00",
        "</sub>": "\x00S2\x00",
        "<br/>": "\x00BR\x00",
        "<br>": "\x00BR\x00",
    }
    for src, token in placeholders.items():
        text = text.replace(src, token)
    text = escape(text)
    text = (
        text.replace("\x00B1\x00", "<b>")
        .replace("\x00B2\x00", "</b>")
        .replace("\x00I1\x00", "<i>")
        .replace("\x00I2\x00", "</i>")
        .replace("\x00C1\x00", '<font name="Courier" size="9">')
        .replace("\x00C2\x00", "</font>")
        .replace("\x00U1\x00", "<super>")
        .replace("\x00U2\x00", "</super>")
        .replace("\x00S1\x00", "<sub>")
        .replace("\x00S2\x00", "</sub>")
        .replace("\x00BR\x00", "<br/>")
    )
    return text


def _normalize_math_markup(text: str) -> str:
    """去掉残留 $$ 定界符，把常见 LaTeX 片段尽量显示为可读文本。"""
    text = re.sub(r"\$\$([^$]+)\$\$", r"\1", text)
    text = re.sub(r"(?<!\$)\$(?!\$)([^$\n]+)\$(?!\$)", r"\1", text)
    replacements = [
        (r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)"),
        (r"\\mathbf\{([^{}]+)\}", r"\1"),
        (r"\\mathrm\{([^{}]+)\}", r"\1"),
        (r"\\text\{([^{}]+)\}", r"\1"),
        (r"\\left\(", "("),
        (r"\\right\)", ")"),
        (r"\\left\[", "["),
        (r"\\right\]", "]"),
        (r"\\times", "×"),
        (r"\\cdot", "·"),
        (r"\\ldots", "…"),
        (r"\\dots", "…"),
        (r"\\infty", "∞"),
        (r"\\geq", "≥"),
        (r"\\leq", "≤"),
        (r"\\neq", "≠"),
        (r"\\approx", "≈"),
        (r"\\rightarrow", "→"),
        (r"\\to", "→"),
        (r"\\Longrightarrow", "⟹"),
        (r"\\implies", "⟹"),
        (r"\\iff", "⇔"),
        (r"\\top", "⊤"),
        (r"\\succ", "≻"),
        (r"\\nabla", "∇"),
        (r"\\lambda", "λ"),
        (r"\\mu", "μ"),
        (r"\\theta", "θ"),
        (r"\\rho", "ρ"),
        (r"\\Sigma", "Σ"),
        (r"\\sum", "∑"),
        (r"\\prod", "∏"),
        (r"\\mathbb\{R\}", "ℝ"),
        (r"\\mathbb\{1\}", "𝟙"),
        (r"\\mathbf\{1\}", "𝟙"),
        (r"\\\|", "∥"),
        (r"\\,", " "),
        (r"\\;", " "),
        (r"\\!", ""),
        (r"\\_", "_"),
        (r"\\\{", "{"),
        (r"\\\}", "}"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    text = text.replace("\\\\", "\n")
    return text


class _HtmlBlockParser(HTMLParser):
    """解析 pandoc / 轻量 Markdown 渲染出的 HTML 为 PDF 流式块。"""

    _INLINE_OPEN = {
        "strong": "<strong>",
        "b": "<b>",
        "em": "<em>",
        "i": "<i>",
        "code": "<code>",
        "sup": "<super>",
        "sub": "<sub>",
    }
    _INLINE_CLOSE = {
        "strong": "</strong>",
        "b": "</b>",
        "em": "</em>",
        "i": "</i>",
        "code": "</code>",
        "sup": "</super>",
        "sub": "</sub>",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []
        self._capture: list[str] = []
        self._capture_tag: str | None = None
        self._list_items: list[str] = []
        self._current_li: list[str] = []
        self._in_li = False
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_buf: list[str] = []
        self._in_cell = False
        self._table_has_header = False
        self._in_thead = False
        self._skip_depth = 0  # 跳过 <style>/<script>

    def parse(self, html: str) -> list[dict[str, Any]]:
        body = html
        m = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.I | re.S)
        if m:
            body = m.group(1)
        self.feed(body)
        self._flush_capture()
        return self.blocks

    def _append_inline(self, token: str) -> None:
        if self._in_cell:
            self._cell_buf.append(token)
        elif self._in_li:
            self._current_li.append(token)
        elif self._capture_tag:
            self._capture.append(token)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"style", "script"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if tag == "br":
            self._append_inline("<br/>")
            return

        if tag in self._INLINE_OPEN:
            self._append_inline(self._INLINE_OPEN[tag])
            return

        # span.math / div 等透明容器：文本由 handle_data 收集
        if tag in {"span", "div", "section", "article", "main", "a"}:
            return

        if tag == "hr":
            self._flush_capture()
            self.blocks.append({"type": "hr"})
            return

        if tag == "table":
            self._flush_capture()
            self._in_table = True
            self._table_rows = []
            self._table_has_header = False
            return

        if tag == "thead":
            self._in_thead = True
            return

        if tag == "tr" and self._in_table:
            self._current_row = []
            return

        if tag in {"td", "th"} and self._in_table:
            self._in_cell = True
            self._cell_buf = []
            if tag == "th" or self._in_thead:
                self._table_has_header = True
            return

        if tag in {"h1", "h2", "h3", "p", "pre"}:
            self._flush_capture()
            self._capture_tag = tag
            self._capture = []
            return

        if tag in {"ul", "ol"}:
            self._flush_capture()
            self._stack.append({"type": tag, "items": self._list_items})
            self._list_items = []
            return

        if tag == "li":
            self._in_li = True
            self._current_li = []
            return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"style", "script"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return

        if tag in self._INLINE_CLOSE:
            self._append_inline(self._INLINE_CLOSE[tag])
            return

        if tag in {"span", "div", "section", "article", "main", "a"}:
            return

        if tag == "thead":
            self._in_thead = False
            return

        if tag in {"td", "th"} and self._in_cell:
            cell_text = "".join(self._cell_buf).strip()
            # 压缩单元格内多余空白
            cell_text = re.sub(r"\s+", " ", cell_text)
            self._current_row.append(cell_text)
            self._cell_buf = []
            self._in_cell = False
            return

        if tag == "tr" and self._in_table:
            if self._current_row:
                self._table_rows.append(list(self._current_row))
            self._current_row = []
            return

        if tag == "table" and self._in_table:
            self.blocks.append(
                {
                    "type": "table",
                    "rows": list(self._table_rows),
                    "has_header": self._table_has_header,
                }
            )
            self._in_table = False
            self._table_rows = []
            self._table_has_header = False
            return

        if tag == "li":
            self._list_items.append("".join(self._current_li).strip())
            self._current_li = []
            self._in_li = False
            return

        if tag in {"ul", "ol"}:
            frame = self._stack.pop() if self._stack else {"type": tag}
            self.blocks.append({"type": frame["type"], "items": list(self._list_items)})
            self._list_items = frame.get("items", [])
            return

        if tag in {"h1", "h2", "h3", "p", "pre"} and self._capture_tag == tag:
            text = "".join(self._capture).strip()
            if text:
                out_type = "pre" if tag == "pre" else tag
                self.blocks.append({"type": out_type, "text": text})
            self._capture_tag = None
            self._capture = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_cell:
            self._cell_buf.append(data)
        elif self._in_li:
            self._current_li.append(data)
        elif self._capture_tag:
            self._capture.append(data)

    def _flush_capture(self) -> None:
        if self._capture_tag and self._capture:
            text = "".join(self._capture).strip()
            if text:
                out_type = "pre" if self._capture_tag == "pre" else self._capture_tag
                self.blocks.append({"type": out_type, "text": text})
        self._capture_tag = None
        self._capture = []

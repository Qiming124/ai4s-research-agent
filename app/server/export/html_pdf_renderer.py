# 将渲染后的 HTML 转为 PDF（reportlab）。

from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import Any
from xml.sax.saxutils import escape

_CID_FONT = "STSong-Light"


def build_pdf_from_html(html: str) -> bytes:
    try:
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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
            fontSize=10,
            leading=14,
            leftIndent=10,
            rightIndent=10,
            spaceAfter=6,
        ),
    }

    blocks = _HtmlBlockParser().parse(html)
    story: list[Any] = []
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
            story.append(Paragraph(_para_html(text), styles["code"]))

    if not story:
        story.append(Paragraph(_para_html("（空文档）"), styles["p"]))

    doc.build(story)
    return buf.getvalue()


def build_pdf_from_markdown(markdown: str, *, title: str | None = None) -> bytes:
    from server.export.pandoc_converter import convert_markdown_to_html

    html = convert_markdown_to_html(markdown, title=title)
    return build_pdf_from_html(html)


def _para_html(text: str) -> str:
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
    }
    for src, token in placeholders.items():
        text = text.replace(src, token)
    text = escape(text)
    text = (
        text.replace("\x00B1\x00", "<b>")
        .replace("\x00B2\x00", "</b>")
        .replace("\x00I1\x00", "<i>")
        .replace("\x00I2\x00", "</i>")
        .replace("\x00C1\x00", '<font name="Courier">')
        .replace("\x00C2\x00", "</font>")
    )
    return text


class _HtmlBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []
        self._capture: list[str] = []
        self._capture_tag: str | None = None
        self._list_items: list[str] = []
        self._current_li: list[str] = []
        self._in_li = False

    def parse(self, html: str) -> list[dict[str, Any]]:
        body = html
        m = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.I | re.S)
        if m:
            body = m.group(1)
        self.feed(body)
        self._flush_capture()
        return self.blocks

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
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
        if tag in {"strong", "b", "em", "i", "code"}:
            if self._in_li:
                self._current_li.append(f"<{tag}>")
            elif self._capture_tag:
                self._capture.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"strong", "b", "em", "i", "code"}:
            if self._in_li:
                self._current_li.append(f"</{tag}>")
            elif self._capture_tag:
                self._capture.append(f"</{tag}>")
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
        if self._in_li:
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

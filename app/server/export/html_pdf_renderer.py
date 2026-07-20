# =============================================================================
# HTML → PDF 渲染器（reportlab 排版）。
#
# 职责：
#     1. build_pdf_from_html() 将 HTML 解析为 reportlab Flowable
#     2. 支持标题/段落/列表/表格/代码块及 pandoc 数学 HTML
#     3. build_pdf_from_markdown() 组合 markdown_renderer + 本模块
#
# 架构位置：
#     - 被调用：server/export/pdf_exporter.py
#     - 调用：export/markdown_renderer.py、reportlab 库
#
# 阅读提示：
#     - 新人先看 build_pdf_from_markdown 与 _HtmlToPdfParser
#
# Debug：
#     - 表格溢出 → A4 页宽与 Table 列宽计算
#     - 数学符号缺失 → span.math 解析分支未命中
# =============================================================================

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
    # arXiv / 会议短文体例近似字号（参考 1608.04636 等）：
    # 标题 ~16pt，节名 ~12pt，正文 ~10.5pt，摘要略小；页边距约 20mm。
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
    )

    styles = {
        "h1": ParagraphStyle(
            "H1",
            fontName=_CID_FONT,
            fontSize=16,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=10,
            spaceBefore=4,
        ),
        "h2": ParagraphStyle(
            "H2",
            fontName=_CID_FONT,
            fontSize=12,
            leading=17,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "H3",
            fontName=_CID_FONT,
            fontSize=11,
            leading=15,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "p": ParagraphStyle(
            "Body",
            fontName=_CID_FONT,
            fontSize=10.5,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            firstLineIndent=0,
        ),
        "abstract": ParagraphStyle(
            "Abstract",
            fontName=_CID_FONT,
            fontSize=9.5,
            leading=14,
            alignment=TA_JUSTIFY,
            leftIndent=12,
            rightIndent=12,
            spaceAfter=8,
        ),
        "li": ParagraphStyle(
            "ListItem",
            fontName=_CID_FONT,
            fontSize=10.5,
            leading=15,
            leftIndent=14,
            spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName=_CID_FONT,
            fontSize=8.5,
            leading=12,
            leftIndent=8,
            rightIndent=8,
            spaceAfter=6,
        ),
        "cell": ParagraphStyle(
            "Cell", fontName=_CID_FONT, fontSize=8.5, leading=12, alignment=TA_LEFT
        ),
        "cell_header": ParagraphStyle(
            "CellHeader", fontName=_CID_FONT, fontSize=8.5, leading=12, alignment=TA_LEFT
        ),
    }

    blocks = _HtmlBlockParser().parse(html)
    story: list[Any] = []
    usable_width = A4[0] - 40 * mm

    abstract_mode = False
    for block in blocks:
        kind = block["type"]
        text = block.get("text", "")
        if kind == "h1":
            abstract_mode = False
            story.append(Paragraph(_para_html(text), styles["h1"]))
        elif kind == "h2":
            heading_plain = re.sub(r"<[^>]+>", "", text).strip().lower()
            abstract_mode = heading_plain in {
                "摘要",
                "abstract",
                "abstract（或 ## 摘要）",
            } or heading_plain.startswith("abstract") or heading_plain.startswith("摘要")
            story.append(Paragraph(_para_html(text), styles["h2"]))
        elif kind == "h3":
            abstract_mode = False
            story.append(Paragraph(_para_html(text), styles["h3"]))
        elif kind == "p":
            style = styles["abstract"] if abstract_mode else styles["p"]
            story.append(Paragraph(_para_html(text), style))
        elif kind == "ul":
            abstract_mode = False
            for item in block.get("items", []):
                story.append(Paragraph(f"• {_para_html(item)}", styles["li"]))
            story.append(Spacer(1, 4))
        elif kind == "ol":
            abstract_mode = False
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


def _consume_brace_group(s: str, start: int) -> tuple[str, int] | None:
    """从 start（须为 '{'）解析一层花括号组，返回 (内容, 结束下标)。"""
    if start >= len(s) or s[start] != "{":
        return None
    depth = 0
    i = start
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    return None


def _replace_latex_frac(text: str) -> str:
    """把 \\frac{num}{den} 转为 (num)/(den)，支持分子分母内嵌套花括号。"""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("\\frac", i) and (i + 5 >= n or not text[i + 5].isalpha()):
            j = i + 5
            while j < n and text[j].isspace():
                j += 1
            num = _consume_brace_group(text, j)
            if num is not None:
                    num_body, j = num
                    while j < n and text[j].isspace():
                        j += 1
                    den = _consume_brace_group(text, j)
                    if den is not None:
                        den_body, j = den
                        out.append(
                            f"({_replace_latex_frac(num_body)})/"
                            f"({_replace_latex_frac(den_body)})"
                        )
                        i = j
                        continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _replace_latex_one_arg(text: str, cmd: str, fmt: str) -> str:
    """替换 \\cmd{arg}；fmt 含 {0} 表示参数。支持嵌套花括号。"""
    needle = f"\\{cmd}"
    out: list[str] = []
    i = 0
    n = len(text)
    ln = len(needle)
    while i < n:
        if text.startswith(needle, i) and (i + ln >= n or not text[i + ln].isalpha()):
            j = i + ln
            while j < n and text[j].isspace():
                j += 1
            grp = _consume_brace_group(text, j)
            if grp is not None:
                body, j = grp
                out.append(fmt.format(body))
                i = j
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _normalize_math_markup(text: str) -> str:
    """去掉残留 $$ 定界符，把常见 LaTeX 片段尽量显示为可读文本。

    注意：命令名后使用 (?![a-zA-Z])，避免 \\to 误吃 \\top 变成 →p。
    """
    # 多行 display math
    text = re.sub(r"\$\$(.+?)\$\$", r"\1", text, flags=re.S)
    # 行内 math（允许定界符内换行：pandoc 常把长公式拆行）
    text = re.sub(r"(?<!\$)\$(?!\$)([^$]+?)\$(?!\$)", r"\1", text)

    # 环境与对齐标记
    text = re.sub(r"\\begin\{[a-zA-Z*]+\}", "", text)
    text = re.sub(r"\\end\{[a-zA-Z*]+\}", "", text)
    text = re.sub(r"\\label\{[^{}]*\}", "", text)
    text = re.sub(r"\\tag\{[^{}]*\}", "", text)
    text = text.replace("&amp;", "&")
    text = re.sub(r"(?m)^\s*&=\s*", "= ", text)
    text = re.sub(r"\s*&=\s*", " = ", text)

    # 带花括号参数的命令（先于简单替换；frac 需支持嵌套）
    text = _replace_latex_frac(text)
    # TeX 简写：\frac12 → (1)/(2)
    text = re.sub(r"\\frac\s*(\d)\s*(\d)", r"(\1)/(\2)", text)
    text = re.sub(r"\\frac\s*(\d)\s*\{([^{}]+)\}", r"(\1)/(\2)", text)
    for cmd, fmt in (
        ("operatorname", "{0}"),
        ("mathrm", "{0}"),
        ("mathbf", "{0}"),
        ("mathsf", "{0}"),
        ("mathit", "{0}"),
        ("textrm", "{0}"),
        ("textbf", "{0}"),
        ("textit", "{0}"),
        ("text", "{0}"),
        ("mathcal", "{0}"),
        ("mathscr", "{0}"),
        ("mathfrak", "{0}"),
        ("overline", "{0}"),
        ("underline", "{0}"),
        ("hat", "{0}̂"),
        ("bar", "{0}̄"),
        ("tilde", "{0}̃"),
        ("vec", "{0}⃗"),
        ("dot", "{0}̇"),
        ("sqrt", "√({0})"),
        ("abs", "|{0}|"),
        ("norm", "∥{0}∥"),
    ):
        text = _replace_latex_one_arg(text, cmd, fmt)

    # \\mathbb{X} 常见集合
    bbb = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "1": "𝟙"}
    def _bbb(m: re.Match[str]) -> str:
        return bbb.get(m.group(1), m.group(1))

    text = re.sub(r"\\mathbb\{([A-Za-z0-9])\}", _bbb, text)
    text = re.sub(r"\\mathbf\{1\}", "𝟙", text)

    # 定界符 / 空格
    spaced = [
        (r"\\left\s*", ""),
        (r"\\right\s*", ""),
        (r"\\big+", ""),
        (r"\\Big+", ""),
        (r"\\biggl?", ""),
        (r"\\biggr?", ""),
        (r"\\quad(?![a-zA-Z])", " "),
        (r"\\qquad(?![a-zA-Z])", "  "),
        (r"\\,", " "),
        (r"\\;", " "),
        (r"\\:", " "),
        (r"\\!", ""),
        (r"\\ ", " "),
    ]
    for pattern, repl in spaced:
        text = re.sub(pattern, repl, text)

    # 符号与希腊字母：一律 (?![a-zA-Z])，防止前缀互吃
    # 较长命令优先（rightarrow 先于 to）
    symbols: list[tuple[str, str]] = [
        (r"\\Longrightarrow", "⟹"),
        (r"\\rightarrow", "→"),
        (r"\\leftarrow", "←"),
        (r"\\leftrightarrow", "↔"),
        (r"\\Rightarrow", "⇒"),
        (r"\\Leftarrow", "⇐"),
        (r"\\Leftrightarrow", "⇔"),
        (r"\\implies", "⟹"),
        (r"\\iff", "⇔"),
        (r"\\subseteq", "⊆"),
        (r"\\supseteq", "⊇"),
        (r"\\subset", "⊂"),
        (r"\\supset", "⊃"),
        (r"\\notin", "∉"),
        (r"\\in", "∈"),
        (r"\\times", "×"),
        (r"\\cdot", "·"),
        (r"\\ldots", "…"),
        (r"\\dots", "…"),
        (r"\\cdots", "⋯"),
        (r"\\infty", "∞"),
        (r"\\geqslant", "≥"),
        (r"\\geq", "≥"),
        (r"\\ge", "≥"),
        (r"\\leqslant", "≤"),
        (r"\\leq", "≤"),
        (r"\\le", "≤"),
        (r"\\succeq", "⪰"),
        (r"\\preceq", "⪯"),
        (r"\\neq", "≠"),
        (r"\\approx", "≈"),
        (r"\\not\\equiv", "≢"),
        (r"\\equiv", "≡"),
        (r"\\sim", "∼"),
        (r"\\npropto", "∝̸"),
        (r"\\not\\propto", "∝̸"),
        (r"\\propto", "∝"),
        (r"\\pm", "±"),
        (r"\\mp", "∓"),
        (r"\\oplus", "⊕"),
        (r"\\otimes", "⊗"),
        (r"\\cap", "∩"),
        (r"\\cup", "∪"),
        (r"\\emptyset", "∅"),
        (r"\\varnothing", "∅"),
        (r"\\forall", "∀"),
        (r"\\exists", "∃"),
        (r"\\partial", "∂"),
        (r"\\perp", "⊥"),
        (r"\\mid", "∣"),
        (r"\\vert", "|"),
        (r"\\Vert", "∥"),
        (r"\\langle", "⟨"),
        (r"\\rangle", "⟩"),
        (r"\\lceil", "⌈"),
        (r"\\rceil", "⌉"),
        (r"\\lfloor", "⌊"),
        (r"\\rfloor", "⌋"),
        (r"\\ast", "*"),
        (r"\\star", "⋆"),
        (r"\\circ", "∘"),
        (r"\\bullet", "•"),
        (r"\\dagger", "†"),
        (r"\\square", "□"),
        (r"\\blacksquare", "■"),
        (r"\\Box", "□"),
        (r"\\succ", "≻"),
        (r"\\prec", "≺"),
        (r"\\gg", "≫"),
        (r"\\ll", "≪"),
        (r"\\top", "⊤"),
        (r"\\bot", "⊥"),
        (r"\\to", "→"),
        (r"\\nabla", "∇"),
        (r"\\lambda", "λ"),
        (r"\\Lambda", "Λ"),
        (r"\\mu", "μ"),
        (r"\\nu", "ν"),
        (r"\\theta", "θ"),
        (r"\\Theta", "Θ"),
        (r"\\rho", "ρ"),
        (r"\\sigma", "σ"),
        (r"\\Sigma", "Σ"),
        (r"\\alpha", "α"),
        (r"\\beta", "β"),
        (r"\\gamma", "γ"),
        (r"\\Gamma", "Γ"),
        (r"\\delta", "δ"),
        (r"\\Delta", "Δ"),
        (r"\\epsilon", "ε"),
        (r"\\varepsilon", "ε"),
        (r"\\zeta", "ζ"),
        (r"\\eta", "η"),
        (r"\\kappa", "κ"),
        (r"\\xi", "ξ"),
        (r"\\Xi", "Ξ"),
        (r"\\pi", "π"),
        (r"\\Pi", "Π"),
        (r"\\tau", "τ"),
        (r"\\phi", "φ"),
        (r"\\varphi", "φ"),
        (r"\\Phi", "Φ"),
        (r"\\psi", "ψ"),
        (r"\\Psi", "Ψ"),
        (r"\\omega", "ω"),
        (r"\\Omega", "Ω"),
        (r"\\ell", "ℓ"),
        (r"\\sum", "∑"),
        (r"\\prod", "∏"),
        (r"\\int", "∫"),
        (r"\\lim", "lim"),
        (r"\\min", "min"),
        (r"\\max", "max"),
        (r"\\inf", "inf"),
        (r"\\sup", "sup"),
        (r"\\arg", "arg"),
        (r"\\dim", "dim"),
        (r"\\det", "det"),
        (r"\\ker", "ker"),
        (r"\\rank", "rank"),
        (r"\\tr", "tr"),
        (r"\\log", "log"),
        (r"\\ln", "ln"),
        (r"\\exp", "exp"),
        (r"\\sin", "sin"),
        (r"\\cos", "cos"),
        (r"\\tan", "tan"),
        (r"\\tanh", "tanh"),
        (r"\\sinh", "sinh"),
        (r"\\cosh", "cosh"),
        (r"\\relu", "ReLU"),
        (r"\\not\\in", "∉"),
        (r"\\not\\subset", "⊄"),
        (r"\\\|", "∥"),
        (r"\\_", "_"),
        (r"\\\{", "{"),
        (r"\\\}", "}"),
        (r"\\%", "%"),
        (r"\\#", "#"),
        (r"\\&", "&"),
    ]
    for pattern, repl in symbols:
        # 仅对以字母结尾的命令名加边界，避免 \\|X 因 (?![a-zA-Z]) 漏替换
        if re.search(r"[A-Za-z]$", pattern):
            pattern = pattern + r"(?![a-zA-Z])"
        text = re.sub(pattern, repl, text)

    text = text.replace("\\\\", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
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

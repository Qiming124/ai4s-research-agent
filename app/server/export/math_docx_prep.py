# =============================================================================
# DOCX 导出前的数学 Markdown 预处理。
#
# 职责：
#     1. prepare_markdown_for_docx() 清洗 $$...$$ 与行内 $...$
#     2. 展开 aligned 环境、替换 \\square 为 Unicode ∎
#     3. 降低 Word/WPS OMML 对中文嵌套公式的渲染失败率
#
# 架构位置：
#     - 被调用：server/export/docx_exporter.py
#     - 调用：无（正则与字符串变换）
#
# 阅读提示：
#     - 新人先看 prepare_markdown_for_docx 与 _fix_display_math
#
# Debug：
#     - 公式仍空白 → 检查 _CJK 与 _LATEX_NOISE 规则是否误删内容
# =============================================================================

from __future__ import annotations

import re

_CJK = re.compile(r"[\u4e00-\u9fff]")
_DISPLAY = re.compile(r"\$\$(.+?)\$\$", re.S)
_INLINE = re.compile(r"(?<!\$)\$(?!\$)([^$]+?)\$(?!\$)", re.S)
_ALIGNED = re.compile(
    r"\$\$\s*\\begin\{aligned\}(.*?)\\end\{aligned\}\s*\$\$",
    re.S,
)
_TEXT_CMD = re.compile(r"\\text\{([^{}]*)\}")
_SQUARE = re.compile(r"\$\s*\\(?:square|Blacksquare|blacksquare|Box)\s*\$")


def prepare_markdown_for_docx(markdown: str) -> str:
    """在 pandoc 转 DOCX 前清洗公式，提高 Word 可见性。"""
    text = markdown
    text = _SQUARE.sub("∎", text)
    text = _expand_aligned_blocks(text)
    text = _DISPLAY.sub(_fix_display_math, text)
    text = _INLINE.sub(_fix_inline_math, text)
    # 再次清掉可能残留的独立 QED 公式
    text = _SQUARE.sub("∎", text)
    return text


def _expand_aligned_blocks(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        body = match.group(1)
        rows = re.split(r"\\\\", body)
        out: list[str] = []
        for row in rows:
            row = row.strip()
            if not row:
                continue
            # 去掉列对齐 &，保留 &=
            row = re.sub(r"(?<!\\)&\s*=\s*", " = ", row)
            row = re.sub(r"(?<!\\)&", " ", row)
            row = re.sub(r"\s+", " ", row).strip()
            notes, row = _pull_cjk_text(row)
            piece = f"$${row}$$"
            if notes:
                piece += " " + " ".join(notes)
            out.append(piece)
        return "\n\n".join(out) if out else match.group(0)

    return _ALIGNED.sub(repl, text)


def _pull_cjk_text(body: str) -> tuple[list[str], str]:
    """抽出 \\text{含中文}，避免中文进入 OMML。"""
    notes: list[str] = []

    # 常见断裂写法：\text{不依赖于 } \theta \text{）}
    broken = re.compile(
        r"\\text\{([^{}]*[\u4e00-\u9fff][^{}]*)\}\s*"
        r"(\\[A-Za-z]+|[A-Za-zΘθμσλ]|\$[^$\n]+\$)\s*"
        r"\\text\{([^{}]*)\}"
    )

    def broken_repl(match: re.Match[str]) -> str:
        left, mid, right = match.group(1), match.group(2), match.group(3)
        mid_readable = mid
        if mid.startswith("$"):
            mid_readable = mid.strip("$")
        greek = {
            r"\theta": "θ",
            r"\Theta": "Θ",
            r"\mu": "μ",
            r"\sigma": "σ",
            r"\lambda": "λ",
            r"\alpha": "α",
            r"\beta": "β",
        }
        mid_readable = greek.get(mid_readable, mid_readable.lstrip("\\") if mid_readable.startswith("\\") else mid_readable)
        notes.append(f"{left}{mid_readable}{right}".strip())
        return ""

    cleaned = broken.sub(broken_repl, body)

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        if _CJK.search(inner):
            notes.append(inner.strip())
            return ""
        return match.group(0)

    cleaned = _TEXT_CMD.sub(repl, cleaned)
    cleaned = re.sub(r"[ \t]*\\qquad[ \t]*", " ", cleaned)
    cleaned = re.sub(r"[ \t]*\\quad[ \t]*", " ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = cleaned.strip(" ,;，；")
    return notes, cleaned


def _fix_display_math(match: re.Match[str]) -> str:
    body = match.group(1).strip()
    # 已是 aligned 的由上游处理；这里兜底
    if "\\begin{aligned}" in body:
        return match.group(0)

    # 用 \\qquad 分隔的多条等式 → 拆成多个独立公式
    if "\\qquad" in body:
        parts = [p.strip().rstrip(",") for p in re.split(r"\\qquad", body)]
        if len(parts) >= 2 and sum(1 for p in parts if "=" in p) >= 2:
            chunks: list[str] = []
            for part in parts:
                if not part:
                    continue
                notes, part2 = _pull_cjk_text(part)
                chunk = f"$${part2}$$"
                if notes:
                    chunk += " " + " ".join(notes)
                chunks.append(chunk)
            return "\n\n".join(chunks)

    notes, cleaned = _pull_cjk_text(body)
    # 公式内残留裸中文（极少数）→ 整段改用可读文本，避免 OMML 整块空白
    if _CJK.search(cleaned):
        from server.export.html_pdf_renderer import _normalize_math_markup

        readable = _normalize_math_markup(f"$${cleaned}$$")
        if notes:
            readable = f"{readable} {' '.join(notes)}"
        return readable

    out = f"$${cleaned}$$"
    if notes:
        out += " " + " ".join(notes)
    return out


def _fix_inline_math(match: re.Match[str]) -> str:
    body = match.group(1).strip()
    if body in {r"\square", r"\Blacksquare", r"\blacksquare", r"\Box"}:
        return "∎"
    notes, cleaned = _pull_cjk_text(body)
    if not cleaned.strip():
        return (" ".join(notes)).strip() or "∎"
    if _CJK.search(cleaned):
        from server.export.html_pdf_renderer import _normalize_math_markup

        readable = _normalize_math_markup(f"${cleaned}$")
        if notes:
            readable = f"{readable} {' '.join(notes)}"
        return readable
    out = f"${cleaned}$"
    if notes:
        out += " " + " ".join(notes)
    return out

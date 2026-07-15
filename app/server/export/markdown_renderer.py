# 轻量 Markdown → HTML 渲染（无 pandoc 时回退）。

from __future__ import annotations

import re
from xml.sax.saxutils import escape


def render_markdown_to_html(markdown: str, *, title: str | None = None) -> str:
    lines = markdown.splitlines()
    parts: list[str] = []
    idx = 0
    doc_title = title

    while idx < len(lines):
        line = lines[idx]
        if line.startswith("# ") and doc_title is None:
            doc_title = line[2:].strip()
            idx += 1
            continue
        if line.startswith("# "):
            parts.append(f"<h1>{_inline(line[2:].strip())}</h1>")
            idx += 1
            continue
        if line.startswith("## "):
            parts.append(f"<h2>{_inline(line[3:].strip())}</h2>")
            idx += 1
            continue
        if line.startswith("### "):
            parts.append(f"<h3>{_inline(line[4:].strip())}</h3>")
            idx += 1
            continue
        if re.match(r"^[-*]\s+", line):
            items: list[str] = []
            while idx < len(lines) and re.match(r"^[-*]\s+", lines[idx]):
                items.append(f"<li>{_inline(lines[idx][2:].strip())}</li>")
                idx += 1
            parts.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", line):
            items = []
            while idx < len(lines) and re.match(r"^\d+\.\s+", lines[idx]):
                item = re.sub(r"^\d+\.\s+", "", lines[idx]).strip()
                items.append(f"<li>{_inline(item)}</li>")
                idx += 1
            parts.append("<ol>" + "".join(items) + "</ol>")
            continue
        if line.strip().startswith("```"):
            idx += 1
            code_lines: list[str] = []
            while idx < len(lines) and not lines[idx].strip().startswith("```"):
                code_lines.append(escape(lines[idx]) + "\n")
                idx += 1
            if idx < len(lines):
                idx += 1
            parts.append(f"<pre><code>{''.join(code_lines)}</code></pre>")
            continue
        if "|" in line and idx + 1 < len(lines) and _looks_like_table_sep(lines[idx + 1]):
            table_html, idx = _consume_table(lines, idx)
            parts.append(table_html)
            continue
        if not line.strip():
            idx += 1
            continue

        para_lines = [line.strip()]
        idx += 1
        while idx < len(lines) and lines[idx].strip() and not _is_block_start(lines[idx]):
            para_lines.append(lines[idx].strip())
            idx += 1
        parts.append(f"<p>{_inline(' '.join(para_lines))}</p>")

    body = "\n".join(parts) if parts else "<p>（空文档）</p>"
    heading = escape(doc_title or title or "研究报告")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        f"<title>{heading}</title></head><body>{body}</body></html>"
    )


def _is_block_start(line: str) -> bool:
    return bool(
        line.startswith("#")
        or re.match(r"^[-*]\s+", line)
        or re.match(r"^\d+\.\s+", line)
        or line.strip().startswith("```")
        or ("|" in line and _looks_like_table_row(line))
    )


def _looks_like_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") or (s.count("|") >= 2)


def _looks_like_table_sep(line: str) -> bool:
    s = line.strip().strip("|")
    if not s or "|" not in line:
        return False
    cells = [c.strip() for c in s.split("|")]
    return all(re.fullmatch(r":?-{3,}:?", c or "-") for c in cells if c is not None)


def _split_table_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _consume_table(lines: list[str], idx: int) -> tuple[str, int]:
    header = _split_table_cells(lines[idx])
    idx += 1
    if idx < len(lines) and _looks_like_table_sep(lines[idx]):
        idx += 1
    body_rows: list[list[str]] = []
    while idx < len(lines) and _looks_like_table_row(lines[idx]) and not _looks_like_table_sep(lines[idx]):
        body_rows.append(_split_table_cells(lines[idx]))
        idx += 1
    th = "".join(f"<th>{_inline(c)}</th>" for c in header)
    rows_html = [f"<tr>{th}</tr>"]
    for row in body_rows:
        td = "".join(f"<td>{_inline(c)}</td>" for c in row)
        rows_html.append(f"<tr>{td}</tr>")
    return f"<table><thead>{rows_html[0]}</thead><tbody>{''.join(rows_html[1:])}</tbody></table>", idx


def _inline(text: str) -> str:
    out = escape(text)
    # 轻量公式：$...$ → 纯文本（PDF 路径会再做Unicode近似）
    out = re.sub(r"\$\$([^$]+)\$\$", r"\1", out)
    out = re.sub(r"(?<!\$)\$(?!\$)([^$\n]+)\$(?!\$)", r"\1", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", out)
    return out

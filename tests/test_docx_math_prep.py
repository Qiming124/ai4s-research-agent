# DOCX 数学预处理与导出可见性测试。

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

import pytest

from server.export.math_docx_prep import prepare_markdown_for_docx
from server.export.docx_exporter import build_docx_bytes


def _omath_texts(docx_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(BytesIO(docx_bytes)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
    out = []
    for m in root.findall(f".//{M}oMath"):
        parts = []
        for t in m.findall(f".//{M}t"):
            if t.text:
                parts.append(t.text)
        out.append("".join(parts))
    return out


def _plain_texts(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(BytesIO(docx_bytes)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return "".join(t.text or "" for t in root.findall(f".//{W}t"))


def test_prep_strips_cjk_text_from_math():
    md = r"$$H = \frac{1}{n}X^\top X \quad \text{（常矩阵，不依赖于 } \theta \text{）}$$"
    out = prepare_markdown_for_docx(md)
    assert "常矩阵" in out
    assert "常矩阵" not in re.search(r"\$\$(.+?)\$\$", out, re.S).group(1)
    assert r"\frac{1}{n}" in out


def test_prep_expands_aligned():
    md = r"""$$\begin{aligned}
a &= b \\
&= c
\end{aligned}$$"""
    out = prepare_markdown_for_docx(md)
    assert r"\begin{aligned}" not in out
    assert out.count("$$") >= 4


def test_prep_splits_qquad_equations():
    md = r"$$\nabla L = A, \qquad H = B$$"
    out = prepare_markdown_for_docx(md)
    assert out.count("$$") >= 4


def test_prep_square_to_qed():
    assert "∎" in prepare_markdown_for_docx(r"证明结束。$\square$")
    assert r"\square" not in prepare_markdown_for_docx(r"$\square$")


def test_docx_no_cjk_inside_omath():
    md = r"""# T

$$\nabla L_{\mathrm{lin}}(\theta) = \frac{1}{n}X^\top(X\theta - y), \qquad H_{\mathrm{lin}}(\theta) = \frac{1}{n}X^\top X \quad \text{（常矩阵）}$$

证明完毕。$\square$
"""
    data = build_docx_bytes(markdown=md)
    maths = _omath_texts(data)
    assert maths, "expected OMML formulas"
    for t in maths:
        assert not re.search(r"[\u4e00-\u9fff]", t), t
        assert "▫" not in t
    plain = _plain_texts(data)
    assert "常矩阵" in plain
    assert "∎" in plain


def test_docx_frac_survives():
    md = r"# T\n\n$$L = \frac{1}{2n}\\sum_{i=1}^n r_i^2$$\n".replace("\\\\", "\\")
    # clearer
    md = "# T\n\n$$L = \\frac{1}{2n}\\sum_{i=1}^n r_i^2$$\n"
    data = build_docx_bytes(markdown=md)
    with zipfile.ZipFile(BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode()
    assert "<m:f>" in xml

# PDF 导出回归：Markdown 表格与公式不得被 HTML→PDF 路径丢弃。

from __future__ import annotations

import io

import pytest

from server.export.html_pdf_renderer import build_pdf_from_html, build_pdf_from_markdown

# 与会话 test-websearch 导出内容同构的最小样例
_TEST_WEB_MD = """# test-web

## 定理：定理 1: （Hessian 最小特征值与临界点类型的关系）

**陈述**：在假设 A1（$C^2$）、A6（有限样本）下，对经验损失 $L(\\theta)$ 的临界点 $\\theta^*$：

| $\\lambda_{\\min}(H(\\theta^*))$ | 临界点类型 |
|:---|:---|
| $\\lambda_{\\min} > 0$ | **严格局部极小点** |
| $\\lambda_{\\min} < 0$ | **严格鞍点**（存在下降方向） |
| $\\lambda_{\\min} = 0$ | **退化临界点**（需高阶分析） |

当额外满足 A4（PL 条件）时，任意满足 $\\lambda_{\\min} > 0$ 的临界点必为**全局极小点**。

## 边界条件与反例

| 条件 | 失效场景 |
|:---|:---|
| A1 ($C^2$) | ReLU 网络在原点 Hessian 不存在 |
| $\\lambda_{\\min}=0$ | 浅层 MLP 原点：Hessian 零矩阵 |
"""


def _pdf_text(pdf_bytes: bytes) -> str:
    pytest.importorskip("pypdf")
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def test_pdf_keeps_markdown_tables():
    pdf = build_pdf_from_markdown(_TEST_WEB_MD, title="test-web")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 2000
    text = _pdf_text(pdf)
    assert "严格局部极小点" in text
    assert "严格鞍点" in text
    assert "退化临界点" in text
    assert "ReLU" in text or "Hessian" in text
    assert "全局极小点" in text


def test_pdf_table_from_raw_html():
    html = """
    <html><body>
    <h1>Demo</h1>
    <table>
      <thead><tr><th>条件</th><th>结论</th></tr></thead>
      <tbody>
        <tr><td><span class="math inline"><em>λ</em><sub>min</sub> &gt; 0</span></td>
            <td><strong>局部极小</strong></td></tr>
      </tbody>
    </table>
    <p>尾注</p>
    </body></html>
    """
    pdf = build_pdf_from_html(html)
    text = _pdf_text(pdf)
    assert "局部极小" in text
    assert "条件" in text
    assert "尾注" in text

# 导出路径数学公式规范化单元测试。

from __future__ import annotations

import pytest

from server.export.html_pdf_renderer import _normalize_math_markup as n


@pytest.mark.parametrize(
    "src, expect_substr, forbid",
    [
        (r"$X^\top X$", "X^⊤ X", ["→p", r"\top"]),
        (r"$\theta \in \mathbb{R}^d$", "θ ∈ ℝ^d", [r"\in", r"\theta"]),
        (r"$\operatorname{rank}(X)$", "rank(X)", [r"\operatorname"]),
        (r"$\lambda_{\min}^+(G)$", "λ_{min}^+(G)", [r"\min", r"\lambda"]),
        (
            r"$\mu = \frac{\sigma_{\min}^+(X^\top X)}{n}$",
            "(σ_{min}^+(X^⊤ X))/(n)",
            [r"\frac", "→p", r"\sigma"],
        ),
        (
            r"$$\begin{aligned} a &= b \\ c &= d \end{aligned}$$",
            "a = b",
            [r"\begin", r"\end"],
        ),
        (r"$\nabla L_{\mathrm{lin}}(\theta)$", "∇ L_{lin}(θ)", [r"\nabla", r"\mathrm"]),
        (r"$\theta \to \infty$", "θ → ∞", [r"\to", r"\infty"]),
        (r"$A \subset B$", "A ⊂ B", [r"\subset"]),
        (r"$\square$", "□", [r"\square"]),
    ],
)
def test_normalize_math_cases(src: str, expect_substr: str, forbid: list[str]):
    out = n(src)
    assert expect_substr in out, f"expected {expect_substr!r} in {out!r}"
    for bad in forbid:
        assert bad not in out, f"forbidden {bad!r} still in {out!r}"


def test_to_does_not_eat_top():
    assert "→p" not in n(r"$M^\top$")
    assert "⊤" in n(r"$M^\top$")


def test_multiline_inline_math_from_pandoc():
    src = "$\\frac{1}{2n}(\\theta^\\top X^\\top X\\theta - 2y^\\top\nX\\theta + y^\\top y)$"
    out = n(src)
    assert "$" not in out
    assert r"\frac" not in out
    assert "⊤" in out
    assert "→p" not in out


def test_frac_shorthand_and_ge():
    assert r"\frac" not in n(r"$\frac12 x$")
    assert "≥" in n(r"$a \ge b$")
    assert "⪰" in n(r"$H \succeq 0$")
    assert "∥" in n(r"$\|x\|$")

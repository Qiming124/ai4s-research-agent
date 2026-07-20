# =============================================================================
# Pandoc 格式转换（Markdown → DOCX / PDF）。
#
# 职责：
#     1. pandoc_available() 检测系统 pandoc 可执行文件
#     2. convert_markdown_to_docx / convert_markdown_to_pdf 子进程调用
#     3. convert_bytes() 通用字节流格式互转
#
# 架构位置：
#     - 被调用：server/export/docx_exporter.py、pdf_exporter.py
#     - 调用：subprocess + 临时目录
#
# 阅读提示：
#     - 新人先看 pandoc_available 与 convert_markdown_to_docx
#
# Debug：
#     - RuntimeError pandoc 未安装 → which pandoc 为空
#     - PDF 失败 → 缺少 xelatex 或字体配置
# =============================================================================

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def convert_bytes(data: bytes, from_fmt: str, to_fmt: str) -> bytes:
    """用 pandoc 将 data 从 from_fmt 转为 to_fmt。"""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("pandoc 未安装。请执行: apt install pandoc")

    with tempfile.TemporaryDirectory() as tmp:
        ext = "md" if from_fmt == "markdown" else from_fmt
        src = Path(tmp) / f"input.{ext}"
        out = Path(tmp) / f"output.{to_fmt}"
        src.write_bytes(data)
        base_cmd = [pandoc, str(src), "-f", from_fmt, "-t", to_fmt, "-o", str(out)]
        if to_fmt != "pdf":
            _run_pandoc(base_cmd, cwd=tmp)
            return out.read_bytes()

        errors: list[str] = []
        for extra in (
            ["--pdf-engine=xelatex", "-V", "CJKmainfont=Noto Sans CJK SC"],
            ["--pdf-engine=xelatex", "-V", "CJKmainfont=Noto Sans SC"],
            ["--pdf-engine=xelatex"],
            [],
        ):
            try:
                _run_pandoc(base_cmd + extra, cwd=tmp)
                return out.read_bytes()
            except RuntimeError as exc:
                errors.append(str(exc))
                if out.exists():
                    out.unlink()
        raise RuntimeError("; ".join(errors[-2:]))


def convert_markdown_to_docx(markdown: str) -> bytes:
    return convert_bytes(markdown.encode("utf-8"), "markdown", "docx")


def convert_markdown_to_html(markdown: str, *, title: str | None = None) -> str:
    """将 Markdown 渲染为 HTML（标题/列表/加粗等结构化输出）。"""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        from server.export.markdown_renderer import render_markdown_to_html

        return render_markdown_to_html(markdown, title=title)

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "input.md"
        out = Path(tmp) / "output.html"
        src.write_text(markdown, encoding="utf-8")
        cmd = [pandoc, str(src), "-f", "markdown", "-t", "html5", "-o", str(out)]
        if title:
            cmd.extend(["--metadata", f"title={title}"])
        _run_pandoc(cmd, cwd=tmp)
        return out.read_text(encoding="utf-8")


def convert_markdown_to_pdf(markdown: str) -> bytes:
    return convert_bytes(markdown.encode("utf-8"), "markdown", "pdf")


def _run_pandoc(cmd: list[str], cwd: str | Path) -> None:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("pandoc 转换超时") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err or "pandoc 转换失败")

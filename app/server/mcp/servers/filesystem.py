# MCP Server：受限目录内的文件读写。

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem")


from shared.paths import DATA_ROOT


def _allowed_roots() -> list[Path]:
    raw = os.environ.get("MCP_ALLOWED_DIRS", str(DATA_ROOT / "mcp_files")).strip()
    if not raw:
        raw = str(DATA_ROOT / "mcp_files")
    return [Path(p).resolve() for p in raw.split(":") if p.strip()]


def _resolve_safe(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        roots = _allowed_roots()
        if not roots:
            raise ValueError("未配置 MCP_ALLOWED_DIRS")
        candidate = (roots[0] / candidate).resolve()
    else:
        candidate = candidate.resolve()

    for root in _allowed_roots():
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    raise ValueError(f"路径不在允许目录内: {path}")


@mcp.tool()
def read_file(path: str) -> str:
    """读取允许目录内的文本文件。

    Args:
        path: 相对或绝对文件路径
    """
    target = _resolve_safe(path)
    if not target.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")
    return target.read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """写入允许目录内的文本文件（自动创建父目录）。

    Args:
        path: 相对或绝对文件路径
        content: 文件内容
    """
    target = _resolve_safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {target}（{len(content)} 字符）"


@mcp.tool()
def list_files(directory: str = ".") -> str:
    """列出允许目录内的文件。

    Args:
        directory: 相对或绝对目录路径
    """
    target = _resolve_safe(directory)
    if not target.is_dir():
        raise NotADirectoryError(f"目录不存在: {directory}")
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
    return "\n".join(entries) if entries else "(空目录)"


def main() -> None:
    for root in _allowed_roots():
        root.mkdir(parents=True, exist_ok=True)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

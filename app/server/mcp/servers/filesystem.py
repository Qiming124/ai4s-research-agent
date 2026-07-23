# =============================================================================
# MCP Server：受限目录内的文件读写。
#
# 默认允许：data/mcp_files + data/projects/*/experiments
# 禁止：data/theory 种子、课题 theory/ 下 symbols/assumptions 等
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem")

from shared.paths import DATA_ROOT


def _allowed_roots() -> list[Path]:
    default = f"{DATA_ROOT / 'mcp_files'}:{DATA_ROOT / 'projects'}"
    raw = os.environ.get("MCP_ALLOWED_DIRS", default).strip() or default
    return [Path(p).resolve() for p in raw.split(":") if p.strip()]


def _is_blocked_theory_path(candidate: Path) -> str | None:
    cand_s = candidate.as_posix()
    if "/data/theory/" in cand_s or cand_s.endswith("/data/theory"):
        return "理论种子目录 data/theory 已禁止访问"
    banned = (
        "assumptions.md",
        "symbols.md",
        "review-checklist.md",
        "assumption-matrix.md",
        "assumption_matrix.md",
    )
    if any(f"/theory/{name}" in cand_s or cand_s.endswith(f"/theory/{name}") for name in banned):
        return "已下线的理论工作区文件禁止访问"
    return None


def _resolve_safe(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        roots = _allowed_roots()
        if not roots:
            raise ValueError("未配置 MCP_ALLOWED_DIRS")
        candidate = (roots[0] / candidate).resolve()
    else:
        candidate = candidate.resolve()

    blocked = _is_blocked_theory_path(candidate)
    if blocked:
        raise ValueError(f"{blocked}: {path}")

    for root in _allowed_roots():
        try:
            rel = candidate.relative_to(root)
        except ValueError:
            continue
        root_s = root.as_posix()
        if root_s.rstrip("/").endswith("/projects"):
            parts = rel.as_posix().split("/")
            # projects/{project_id}/experiments/...
            if len(parts) < 2 or parts[1] != "experiments":
                raise ValueError(f"仅允许访问 projects/*/experiments：{path}")
        return candidate
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
    return f"已写入: {target}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """列出允许目录内的文件与子目录。

    Args:
        path: 相对或绝对目录路径
    """
    target = _resolve_safe(path)
    if not target.is_dir():
        raise NotADirectoryError(f"不是目录: {path}")
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = []
    for entry in entries:
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{entry.name}{suffix}")
    return "\n".join(lines) if lines else "(空目录)"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

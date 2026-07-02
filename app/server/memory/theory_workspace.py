# 理论工作区：从 data/theory/ 加载符号表、假设等并注入 prompt。

from __future__ import annotations

from pathlib import Path

from server.config import Settings, get_settings
from shared.paths import THEORY_DIR

_MAX_CHARS = 4000


def _read_workspace_file(path: Path, max_chars: int = _MAX_CHARS) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n...(截断)"
    return text


def get_theory_workspace_path(settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    return Path(cfg.theory_workspace_path)


def load_symbols(settings: Settings | None = None) -> str:
    root = get_theory_workspace_path(settings)
    return _read_workspace_file(root / "symbols.md")


def load_assumptions(settings: Settings | None = None) -> str:
    root = get_theory_workspace_path(settings)
    return _read_workspace_file(root / "assumptions.md")


def load_review_checklist(settings: Settings | None = None) -> str:
    root = get_theory_workspace_path(settings)
    return _read_workspace_file(root / "review-checklist.md")


def format_workspace_context(settings: Settings | None = None) -> str:
    """将理论工作区核心文件格式化为可注入 system prompt 的文本。"""
    symbols = load_symbols(settings)
    assumptions = load_assumptions(settings)
    if not symbols and not assumptions:
        return ""

    parts = ["## 项目理论工作区（符号与假设须保持一致）"]
    if symbols:
        parts.append("### 符号表\n" + symbols)
    if assumptions:
        parts.append("### 全局假设\n" + assumptions)
    return "\n\n".join(parts)


def list_workspace_files(settings: Settings | None = None) -> list[dict[str, str]]:
    """列出理论工作区相对路径与类型（供 API）。"""
    root = get_theory_workspace_path(settings)
    if not root.is_dir():
        return []
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            rel = str(path.relative_to(root))
            files.append({"path": rel, "kind": "file"})
    return files

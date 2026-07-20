# =============================================================================
# 理论工作区：按课题隔离的符号表、假设与 prompt 注入。
#
# 职责：
#     1. 读写 data/theory/{project_id}/ 下 symbols.md、assumptions.md 等
#     2. format_workspace_context() 截断后注入 system prompt
#     3. resolve_project_id() 统一 default 别名
#
# 架构位置：
#     - 被调用：server/api/theory.py、memory/structured/injection.py、graph.py
#     - 调用：shared/paths.DATA_ROOT、THEORY_DIR
#
# 阅读提示：
#     - 新人先看 get_theory_workspace_path、load_symbols、format_workspace_context
#
# Debug：
#     - 工作区为空 → 目录或文件不存在，非 bug
#     - prompt 过长 → _MAX_CHARS 截断，调高需谨慎
# =============================================================================

from __future__ import annotations

from pathlib import Path

from server.config import Settings, get_settings
from shared.paths import DATA_ROOT, THEORY_DIR

_MAX_CHARS = 4000


def _read_workspace_file(path: Path, max_chars: int = _MAX_CHARS) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n...(截断)"
    return text


def resolve_project_id(project_id: str | None = None) -> str:
    pid = (project_id or "").strip() or "default"
    return pid


def get_theory_workspace_path(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> Path:
    """返回课题理论工作区根目录（优先 projects.workspace_path）。"""
    pid = resolve_project_id(project_id)
    try:
        from server.memory.projects import get_project_store

        store = get_project_store()
        project = store.get_project(pid)
        if project and project.get("workspace_path"):
            root = Path(project["workspace_path"])
            root.mkdir(parents=True, exist_ok=True)
            return root
        return store.ensure_workspace(pid)
    except Exception:
        # 回退：data/projects/{id}/theory；若仍空则用全局种子目录只读场景
        root = DATA_ROOT / "projects" / pid / "theory"
        if root.is_dir() or pid == "default":
            root.mkdir(parents=True, exist_ok=True)
            return root
        cfg = settings or get_settings()
        return Path(cfg.theory_workspace_path)


def load_symbols(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> str:
    root = get_theory_workspace_path(settings, project_id=project_id)
    text = _read_workspace_file(root / "symbols.md")
    if text:
        return text
    # 工作区尚未播种时回退全局种子（只读）
    return _read_workspace_file(THEORY_DIR / "symbols.md")


def load_assumptions(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> str:
    root = get_theory_workspace_path(settings, project_id=project_id)
    text = _read_workspace_file(root / "assumptions.md")
    if text:
        return text
    return _read_workspace_file(THEORY_DIR / "assumptions.md")


def load_review_checklist(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> str:
    root = get_theory_workspace_path(settings, project_id=project_id)
    text = _read_workspace_file(root / "review-checklist.md")
    if text:
        return text
    return _read_workspace_file(THEORY_DIR / "review-checklist.md")


def format_workspace_context(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> str:
    """将理论工作区核心文件格式化为可注入 system prompt 的文本。"""
    symbols = load_symbols(settings, project_id=project_id)
    assumptions = load_assumptions(settings, project_id=project_id)
    if not symbols and not assumptions:
        return ""

    parts = ["## 项目理论工作区（符号与假设须保持一致）"]
    if symbols:
        parts.append("### 符号表\n" + symbols)
    if assumptions:
        parts.append("### 全局假设\n" + assumptions)
    return "\n\n".join(parts)


def list_workspace_files(
    settings: Settings | None = None,
    project_id: str | None = None,
) -> list[dict[str, str]]:
    """列出理论工作区相对路径与类型（供 API）。"""
    root = get_theory_workspace_path(settings, project_id=project_id)
    if not root.is_dir():
        return []
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            rel = str(path.relative_to(root))
            files.append({"path": rel, "kind": "file"})
    return files

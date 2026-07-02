# LaTeX 导出 API。

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from server.config import get_settings
from server.memory.structured.store import get_structured_memory_store
from shared.schemas import LatexExportRequest, LatexExportResponse

router = APIRouter(tags=["export"])


@router.post("/v1/export/latex", response_model=LatexExportResponse)
async def export_latex(request: LatexExportRequest) -> LatexExportResponse:
    store = get_structured_memory_store()
    entries: list[dict] = []
    if request.session_id:
        entries.extend(store.list_entries(session_id=request.session_id, limit=100))
    if request.include_global:
        entries.extend(store.list_entries(global_only=True, limit=100))

    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath,amsthm}",
        r"\newtheorem{theorem}{定理}",
        r"\newtheorem{lemma}{引理}",
        f"\\title{{{request.title}}}",
        r"\begin{document}",
        r"\maketitle",
    ]
    for entry in entries:
        kind = entry.get("kind", "note")
        title = entry.get("title", "")
        body = entry.get("body", "")
        env = "theorem" if kind == "theorem" else "lemma" if kind == "hypothesis" else "theorem"
        lines.append(f"\\begin{{{env}}}[{title}]")
        lines.append(body.replace("$", "\\$")[:2000])
        lines.append(f"\\end{{{env}}}")
        lines.append("")

    lines.append(r"\end{document}")
    latex = "\n".join(lines)

    out_path: str | None = None
    settings = get_settings()
    proofs_dir = Path(settings.theory_workspace_path) / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    export_file = proofs_dir / "export.tex"
    export_file.write_text(latex, encoding="utf-8")
    out_path = str(export_file)

    return LatexExportResponse(latex=latex, path=out_path)

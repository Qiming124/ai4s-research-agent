#!/usr/bin/env python3
"""本地导出测试实验室：从已收尾会话导出多版本并检查公式/乱码。"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server.export.ai_polish import EXPORT_PRESETS, polish_export_markdown
from server.export.builder import build_markdown_document
from server.export.docx_exporter import build_docx_bytes
from server.export.html_pdf_renderer import build_pdf_from_markdown, _normalize_math_markup
from server.export.pdf_exporter import build_pdf_bytes
from server.memory.structured.store import get_structured_memory_store

LAB = ROOT / "data" / "export_test_lab"
SESSION_ID = "d737474a-4320-4bbf-9f2e-5f83d1b3e28d"
TITLE = "PL条件下经验损失临界点分类"

# 常见乱码 / 坏公式迹象
MOJIBAKE_PATTERNS = [
    r"Ã.",  # UTF-8 misread as Latin-1
    r"â€.",
    r"ï¿½",
    r"\\u00",
    r"ðŸ",
    r"\\\\frac",  # double-escaped
    r"\\\\theta",
]
RAW_LATEX_LEAK = [
    r"\\nabla",
    r"\\theta",
    r"\\frac\{",
    r"\\mathbb",
    r"\\operatorname",
    r"\\text\{",
    r"\\begin\{",
]


def collect_raw_markdown() -> str:
    store = get_structured_memory_store()
    entries = store.list_entries(session_id=SESSION_ID, limit=200)
    if not entries:
        # fallback to previously exported sample
        sample = ROOT / "data" / "export_samples" / "raw_export.md"
        return sample.read_text(encoding="utf-8")
    return build_markdown_document(title=TITLE, entries=entries)


def scan_text(label: str, text: str) -> dict:
    issues: list[str] = []
    for pat in MOJIBAKE_PATTERNS:
        if re.search(pat, text):
            issues.append(f"mojibake:{pat}")
    raw_hits = []
    for pat in RAW_LATEX_LEAK:
        m = re.findall(pat, text)
        if m:
            raw_hits.append(f"{pat}×{len(m)}")
    if raw_hits:
        issues.append("raw_latex:" + ",".join(raw_hits[:8]))
    # replacement char
    if "\ufffd" in text:
        issues.append("replacement_char")
    return {
        "label": label,
        "chars": len(text),
        "headings": len([l for l in text.splitlines() if l.startswith("#")]),
        "dollar_math": len(re.findall(r"\$.*?\$", text, flags=re.S)),
        "issues": issues,
        "ok": not issues,
    }


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages[:4]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def probe_math_normalize() -> list[dict]:
    samples = [
        r"$\nabla L_{\mathrm{lin}}(\theta)$",
        r"$$\frac{1}{2n}\|X\theta - y\|^2$$",
        r"$\theta \in \mathbb{R}^d$",
        r"$\lambda_{\min}^+(G)$",
        r"$\operatorname{rank}(X)$",
    ]
    rows = []
    for s in samples:
        out = _normalize_math_markup(s)
        rows.append({"in": s, "out": out, "still_backslash": "\\" in out})
    return rows


async def polish_variants(raw: str) -> dict[str, str]:
    # 控制长度以加快测试，但仍含足够公式
    chunks = raw.split("\n---\n")
    sample = "\n---\n".join(chunks[:6])
    if len(sample) > 12000:
        sample = sample[:12000]
    out: dict[str, str] = {"raw": raw}
    for key, instr in EXPORT_PRESETS.items():
        polished, ok = await polish_export_markdown(
            title=TITLE, markdown=sample, instructions=instr
        )
        out[key] = polished if ok else sample
        print(f"  polish {key}: applied={ok} chars={len(out[key])}")
    return out


def write_formats(name: str, markdown: str) -> dict:
    folder = LAB / name
    folder.mkdir(parents=True, exist_ok=True)
    md_path = folder / "export.md"
    md_path.write_text(markdown, encoding="utf-8")

    # UTF-8 BOM check / rewrite clean
    md_path.write_text(markdown, encoding="utf-8")

    pdf_path = folder / "export.pdf"
    docx_path = folder / "export.docx"
    html_probe = folder / "probe_math.txt"

    result = {"name": name, "files": {}, "checks": []}

    try:
        pdf = build_pdf_bytes(markdown=markdown)
        pdf_path.write_bytes(pdf)
        result["files"]["pdf"] = len(pdf)
    except Exception as exc:
        result["files"]["pdf_error"] = str(exc)

    try:
        docx = build_docx_bytes(markdown=markdown)
        docx_path.write_bytes(docx)
        result["files"]["docx"] = len(docx)
    except Exception as exc:
        result["files"]["docx_error"] = str(exc)

    # math normalize probe on this doc's formulas
    formulas = re.findall(r"\$\$[^$]+\$\$|\$[^$\n]+\$", markdown)[:20]
    probe_lines = []
    still = 0
    for f in formulas:
        n = _normalize_math_markup(f)
        if "\\" in n:
            still += 1
        probe_lines.append(f"IN:  {f}\nOUT: {n}\n")
    html_probe.write_text("\n".join(probe_lines), encoding="utf-8")
    result["formula_samples"] = len(formulas)
    result["formula_still_latex_cmd"] = still

    md_check = scan_text(f"{name}/md", markdown)
    result["checks"].append(md_check)

    if pdf_path.is_file():
        pdf_text = extract_pdf_text(pdf_path)
        (folder / "pdf_extract.txt").write_text(pdf_text, encoding="utf-8")
        result["checks"].append(scan_text(f"{name}/pdf", pdf_text))
        # glyph missing often shows as empty or ·
        if pdf_text and len(re.findall(r"[θμλ∇ℝ∑∥]", pdf_text)) == 0 and "\\theta" not in markdown:
            # if original had greek via latex, PDF might lose them
            if any(x in markdown for x in ("\\theta", "\\nabla", "θ", "∇")):
                result["checks"][-1]["issues"].append("pdf_missing_greek_or_math_glyphs")
                result["checks"][-1]["ok"] = False

    return result


async def main() -> None:
    LAB.mkdir(parents=True, exist_ok=True)
    print("== collect raw ==")
    raw = collect_raw_markdown()
    (LAB / "raw" / "export.md").parent.mkdir(parents=True, exist_ok=True)
    print(f"raw chars={len(raw)}")

    print("== math normalize unit probe ==")
    unit = probe_math_normalize()
    (LAB / "reports" / "math_normalize_probe.json").write_text(
        json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for row in unit:
        print(" ", "FAIL" if row["still_backslash"] else "OK ", row["out"][:60])

    print("== polish presets ==")
    variants = await polish_variants(raw)

    print("== write formats ==")
    reports = []
    for name, md in variants.items():
        print(f" rendering {name}...")
        reports.append(write_formats(name, md))

    summary = {
        "session_id": SESSION_ID,
        "lab": str(LAB),
        "math_normalize_probe": unit,
        "exports": reports,
    }
    out = LAB / "reports" / "summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # human report
    lines = ["# Export Test Lab Report", "", f"session: `{SESSION_ID}`", ""]
    for r in reports:
        lines.append(f"## {r['name']}")
        lines.append(f"- files: {r.get('files')}")
        lines.append(f"- formulas sampled: {r.get('formula_samples')}, still LaTeX cmds after normalize: {r.get('formula_still_latex_cmd')}")
        for c in r.get("checks", []):
            status = "OK" if c.get("ok") else "ISSUES"
            lines.append(f"- {c['label']}: {status} {c.get('issues')}")
        lines.append("")
    (LAB / "reports" / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("== done ==")
    print((LAB / "reports" / "REPORT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())

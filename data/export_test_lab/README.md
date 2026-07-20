# 导出测试实验室（Export Test Lab）

从已收尾会话导出多版本，检查公式渲染与乱码。

## 位置

`data/export_test_lab/`

| 目录 | 说明 |
|------|------|
| `raw/` | 未 AI 润色的原始 Markdown → PDF/DOCX |
| `arxiv_theory/` | arXiv 理论文风 preset |
| `theorem_catalog/` | 定理目录 preset |
| `abstract_brief/` | 摘要简报 preset |
| `experiment_report/` | 实验报告 preset |
| `reports/` | `REPORT.md` / `DOCX_REPORT.md` / `summary*.json` |

每个版本含：`export.md` / `export.pdf` / `export.docx` / `pdf_extract.txt`

## 运行

```bash
cd /home/agent
PYTHONPATH=app .venv/bin/python scripts/export_test_lab.py
```

默认会话：`d737474a-4320-4bbf-9f2e-5f83d1b3e28d`（可在脚本内改 `SESSION_ID`）。

## 检查项

- 乱码：UTF-8 误读痕迹（Ã、â€、ï¿½）
- PDF 泄漏：未消化的 `\\frac` / `\\theta` / `\\begin` / `→p` 等
- DOCX：OMML 内不得含中文；`\\square` 不得变成 `▫`；`\\frac` 数量应进入 `m:f`；见 `reports/DOCX_REPORT.md`
- 公式规范化：`tests/test_math_normalize.py`、`tests/test_docx_math_prep.py`

# 导出测试实验室（Export Test Lab）

历史导出抽检报告目录。生成脚本已从仓库移除；如需复测，请直接调用导出 API（`/v1/export/*`）或运行 `tests/test_math_normalize.py` / `tests/test_docx_math_prep.py`。

## 位置

`data/export_test_lab/reports/` — 保留 `REPORT.md` / `DOCX_REPORT.md` 作为既往检查记录参考。

## 检查项（手工或单测）

- 乱码：UTF-8 误读痕迹（Ã、â€、ï¿½）
- PDF 泄漏：未消化的 `\\frac` / `\\theta` / `\\begin` / `→p` 等
- DOCX：OMML 内不得含中文；见 `reports/DOCX_REPORT.md`
- 公式规范化：`tests/test_math_normalize.py`、`tests/test_docx_math_prep.py`

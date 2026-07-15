# 多论文流水线测试对照 — 2026-07-15

范围：3 篇损失景观 / 局部极小 / PL 相关论文；完整 `/research`；`enable_tools=false`。
成功判定：SSE `pipeline_stage=complete`；`iterate@S7` 视为流水线跑通但审稿卡门（与 BCE 复测一致）。

| arXiv | 题目概要 | PID | SID | CID | 入库 | 终态 | 耗时 | S1 | S3 | S5 | S7 | 定理数 | MD/PDF | report |
|-------|----------|-----|-----|-----|------|------|------|----|----|----|----|--------|--------|--------|
| 1902.02366 | Negative eigenvalues of the Hessian in d | `cd9c37f7-5cc` | `ll-1902-02366-20260715-0839` | `eb44e1e9-bd9` | ok | `iterate@S7_review` | 492.7s | pass | pass | fail | fail | 19 | md=200/40753; pdf=200/50172 magic=True | True |
| 1608.04636 | Linear Convergence under Polyak-Lojasiew | `d1b098a9-323` | `ll-1608-04636-20260715-0853` | `37b9b7d3-23b` | ok | `iterate@S7_review` | 345.8s | pass | pass | fail | fail | 10 | md=200/12132; pdf=200/15930 magic=True | True |
| 1412.0233 | The Loss Surfaces of Multilayer Networks | `2d39a895-015` | `ll-1412-0233-20260715-0904` | `74d142cf-1f4` | ok | `iterate@S7_review` | 342.1s | pass | pass | fail | fail | 9 | md=200/19862; pdf=200/24378 magic=True | True |

## 分篇备注

### arXiv:1902.02366
- 产物目录: `/home/agent/data/campaigns/cd9c37f7-5cc/eb44e1e9-bd9`
- 形式化问题: `/home/agent/data/theory/campaigns/eb44e1e9-bd9-problem.md`
- 冒烟: 定理 19 条（含数学标记=True）；导出 MD/PDF 均 200
- SSE complete: True
- 备注: S5 DB=fail（实验未全部通过）、SSE 门常显示 pass；S7 因审稿含「致命」关键词 → status=iterate，未进 S8

### arXiv:1608.04636
- 产物目录: `/home/agent/data/campaigns/d1b098a9-323/37b9b7d3-23b`
- 形式化问题: `/home/agent/data/theory/campaigns/37b9b7d3-23b-problem.md`
- 冒烟: 定理 10 条（含数学标记=True）；导出 MD/PDF 均 200
- SSE complete: True
- 备注: S5 DB=fail（实验未全部通过）、SSE 门常显示 pass；S7 因审稿含「致命」关键词 → status=iterate，未进 S8

### arXiv:1412.0233
- 产物目录: `/home/agent/data/campaigns/2d39a895-015/74d142cf-1f4`
- 形式化问题: `/home/agent/data/theory/campaigns/74d142cf-1f4-problem.md`
- 冒烟: 定理 9 条（含数学标记=True）；导出 MD/PDF 均 200
- SSE complete: True
- 备注: S5 DB=fail（实验未全部通过）、SSE 门常显示 pass；S7 因审稿含「致命」关键词 → status=iterate，未进 S8

## 结论

1. **基建通过**：三篇均入库成功，SSE 均收到 `pipeline_stage=complete`，均有 `report.md`，定理库与 MD/PDF 导出冒烟通过。
2. **终态一致**：三篇均为 `iterate@S7_review`（S1/S3 pass，S5 fail，S7 fail）——与此前 BCE(2505.05813) 两次复测模式相同。
3. **未达 `done`**：审稿门对「致命」敏感；S5 严格门未全部过关。属科研质量门，非 API 中断。

## 原始结果 JSON

- `/tmp/multi_paper_runs/1902-02366-result.json`
- `/tmp/multi_paper_runs/1608-04636-result.json`
- `/tmp/multi_paper_runs/1412-0233-result.json`

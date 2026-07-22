# AI4S Agent 功能验收测试方案

> 版本：v1.0 · 日期：2026-07-22  
> 适用范围：[`/home/agent`](../..) v2.2 理论侧科研助手  
> 执行脚本：[`scripts/run_acceptance_suite.py`](../../scripts/run_acceptance_suite.py)  
> 结果目录：本目录 `ACCEPTANCE-RESULTS-*.json` / `ACCEPTANCE-REPORT.md`

## 1. 定位与目标

系统定位：**深度领域科研助手**——文献检索/阅读 → 理论证明 → 结合实验方法与数据给出下一步实验方向。

统一判定：`PASS` / `PARTIAL` / `FAIL` / `SKIP` / `N/A`。

**不测**：方法卡（MethodCard）整条链路 → `SKIP`。

## 2. 三层结构

1. **L1** API/服务冒烟  
2. **L2** 功能清单（文献 / 理论 / 产出 / 课题会话 / Chat）  
3. **L3** 黄金科研路径（文献→推导→实验指导→导出）

## 3. 环境与夹具

```bash
# 启动（若未运行）
source .venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000 --app-dir app

# 夹具
ls data/acceptance_fixtures/
# loss_notes.pdf / loss_notes.docx / loss_landscape_notes.md
# theorem_import.md / metrics_plateau.csv

# 一键验收
python scripts/run_acceptance_suite.py
```

夹具唯一 RAG 标记：`ACCEPTANCE_UNIQUE_TOKEN_ZetaHessian991`  
建议 arXiv ID：`1412.0233`

## 4. 用例索引

| 层 | ID 前缀 | 内容 |
|----|---------|------|
| L1 | L1-01..03 | health / pytest / OpenAPI |
| L2-A | A-01..07 | RAG 上传、arXiv、检索、课题隔离、删除 |
| L2-B | B-01..08 | 推导迹、定理 CRUD/导入/上下文、会话隔离、DAG、图谱、工作区 |
| L2-C | C-01..06 | 实验计划、产出共享/隔离、实验记录、导出、润色 |
| L2-D | D-01..04 | 课题/会话、隔离复验、删除会话 |
| L2-E | E-01..07 | MCP arXiv/搜索、提示词优化、模型、路由、chat/math、协同 |
| L3 | G1..G7 / L3 | 黄金路径与总评 |

详细步骤与通过标准见仓库计划文档或运行脚本内断言逻辑。

## 5. 隔离规则（硬验收）

| 规则 | 期望 |
|------|------|
| RAG | 同课题共享，跨课题不共享 |
| 定理库 | 按会话隔离（非 global） |
| 实验产出 | 同课题共享，跨课题不共享 |

## 6. 黄金路径通过标准

- **核心通过**：G2–G6 均至少 PARTIAL，且 G2/G3/G5 中 ≥2 项 PASS  
- **展示可用但不深**：功能多 PASS 但文献/实验建议空泛 → 科研深度 PARTIAL  
- **未通过**：无推导迹 / 完全无视上传数据 / 隔离打破

## 7. 交付物

1. 填写完成的用例结果表（JSON + 报告 Markdown）  
2. 三条隔离规则结论  
3. 黄金路径一句话总评  
4. 新缺陷 / 已知问题 / PARTIAL 列表

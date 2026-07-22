# AI4S Agent 功能验收报告

> 执行日期：2026-07-22（UTC）  
> 环境：本地 `http://127.0.0.1:8000` · 模型 `deepseek-v4-pro`  
> 方案：[`ACCEPTANCE-TEST-PLAN.md`](ACCEPTANCE-TEST-PLAN.md)  
> 原始结果：[`ACCEPTANCE-RESULTS-20260722.json`](ACCEPTANCE-RESULTS-20260722.json)  
> 运行日志：[`ACCEPTANCE-RUN.log`](ACCEPTANCE-RUN.log)  
> 执行器：[`scripts/run_acceptance_suite.py`](../../scripts/run_acceptance_suite.py)

## 总评

**黄金路径结论：核心通过**（文献 RAG → math 推导迹 → 实验数据指导下一步 → 导出/润色）。

| 指标 | 结果 |
|------|------|
| 用例总数 | 37（含方法卡 SKIP 1） |
| PASS | 36 |
| PARTIAL / FAIL | 0（初测 A-07/E-05 已复测纠正） |
| SKIP | 1（方法卡，按方案不测） |

## 隔离三规则

| 规则 | 结论 |
|------|------|
| RAG 同课题共享 | **PASS** |
| RAG 跨课题不共享 | **PASS** |
| 定理库按会话隔离 | **PASS** |
| 实验产出同课题共享 | **PASS** |
| 实验产出跨课题隔离 | **PASS** |

## 分层结果摘要

### L1 冒烟

| ID | 结果 |
|----|------|
| L1-01 健康检查 | PASS（`deepseek-v4-pro`） |
| L1-02 pytest `tests/api` + `tests/e2e` | PASS |
| L1-03 OpenAPI 关键路由 | PASS |

### L2 功能清单

| 模块 | 结论 | 备注 |
|------|------|------|
| A 文献/RAG | 全 PASS | PDF/MD/DOCX/arXiv 入库；标记串可被检索；删除需 `?session_id=` |
| B 理论 | 全 PASS | 推导迹、定理 CRUD/导入/入上下文、DAG、图谱可达、工作区读写可达 |
| C 产出 | 全 PASS | ExperimentPlan、实验 CSV 入库并进入顾问回答、md/latex 导出、AI 润色 |
| D 课题会话 | 全 PASS | 双课题双会话；隔离复验；会话 purge |
| E Chat/MCP | 全 PASS | arXiv/web_search 工具、提示词优化、DeepSeek、路由、chat/math、协同 |
| 方法卡 | SKIP | 按方案跳过 |

### L3 黄金路径

| 阶段 | 结果 |
|------|------|
| G1 立题 | PASS |
| G2 文献 | PASS（RAG 命中唯一标记） |
| G3 理论推导 | PASS |
| G4 假设依赖图 | PASS |
| G5 实验顾问读数 | PASS |
| G6 计划/导出润色 | PASS |
| G7 隔离抽检 | PASS |
| **总评** | **核心通过** |

## 初测问题与复测

| 项 | 初测 | 复测结论 |
|----|------|----------|
| A-07 删除文档 | FAIL | 脚本未传必填查询参数 `session_id`（API 返回 422）。带 `session_id` 删除后文档消失 → **功能 PASS**。已修复执行器。 |
| E-05 多 Agent 路由 | PARTIAL | SSE `meta` 字段为 `agent_name` 而非 `agent`，初测未解析到。复测 literature/theory/experiment 均命中 keyword 路由 → **PASS**。已修复执行器。 |

## 不清 / 体验备注（非阻塞）

| 项 | 说明 |
|----|------|
| B-07 关系图谱 | 接口与节点边可返回；产品用途仍未定义，本轮仅验可达性。 |
| B-08 工作区 | 列表/写入 PASS；「对话中深度引用文件」未做对抗性深测，记体验待加强。 |
| E-04 设置微调 | API 侧确认 DeepSeek 与 agents/mcp 状态；UI 改 temperature 等感知差异建议人工点一次。 |

## 与已知问题对照

对照 [`doc/KNOWN_ISSUES.md`](../KNOWN_ISSUES.md)：

- **C2**（无鉴权 / CORS `*`）：本轮验收环境为本地，未纳入功能 FAIL。
- **H2/H3**（工作区路径、`eval`）：本轮未触发安全回归用例。
- 本轮**未发现**新的阻断级功能缺陷；A-07/E-05 初测失败均属验收脚本问题。

## 夹具

目录：`data/acceptance_fixtures/`

- `loss_notes.pdf` / `loss_notes.docx` / `loss_landscape_notes.md`
- `theorem_import.md` / `metrics_plateau.csv`
- RAG 唯一标记：`ACCEPTANCE_UNIQUE_TOKEN_ZetaHessian991`

## 复现命令

```bash
source .venv/bin/activate
# 确保 uvicorn 已在 :8000
python scripts/run_acceptance_suite.py
```

## 一句话结论

当前 Agent 在「深度领域科研助手」主叙事上：**附属功能清单可用，隔离规则成立，文献→理论推导→实验指导→导出闭环可跑通**；方法卡未测；关系图谱与工作区对话引用仍属体验/产品定义待补强，不阻断核心验收。

# AI4S 理论侧 Agent 功能验收方案

- **日期**：2026-07-22  
- **状态**：已执行（结果见同目录 acceptance-results）  
- **方式**：混合（金路径手工/API + 分项清单 + pytest 冒烟）  
- **定位**：用深度学习解决科学问题的理论侧多智能体——文献 → 理论 → 实验指导（不代训、不以数值实跑为核心）

> 详细步骤与判准见 Cursor plan「Agent acceptance test」。本文为落盘副本，便于与结果表对照。

---

## 隔离模型（实现为准）

| 资产 | 作用域 |
|------|--------|
| RAG 语料 | **课题**共享 |
| RAG 引用轨迹 | **会话** |
| 定理库（UI） | **会话**（另有 global） |
| 假设 DAG | **会话** |
| 理论工作区文件 | **课题** |
| 对话历史 | **会话** |

若产品期望「同课题共享定理」，记为需求缺口，不单列本次回归失败。

---

## A. 金路径

| ID | 步骤 | 通过标准 |
|----|------|----------|
| A1 | 建课题 + 会话 | 会话挂在课题下 |
| A2 | 上传 PDF/MD + arXiv | 文献库有文档 |
| A3 | literature/auto + 文献问答 | SSE + RAG 痕迹 |
| A4 | theory/Math 短推导 | 推导成立；推导迹理想有 |
| A5 | 定理 CRUD + 引用 | 可见；可挂钩上下文 |
| A6 | experiment 实验计划 | 计划可见 |
| A7 | 上传 CSV + 追问 | 有对照解读 |
| A8 | 导出 preview/md/docx | 可下载 |
| A9 | MCP arXiv/搜索 | 工具调用或可诊断失败 |

## B. 分项

- **B1 文献**：L1–L5 测；L6 方法卡 Skip  
- **B2 理论**：T1–T4；T5/T6 探测-only  
- **B3 产出**：O1–O3  
- **B4 课题会话**：P1–P4  
- **B5 Chat**：C1–C7  

## C. 自动化

```bash
pytest tests/api/test_smoke_all.py tests/api/test_documents_full.py \
  tests/api/test_projects_full.py tests/api/test_export_full.py \
  tests/api/test_jupyter_upload.py tests/api/test_prompt_optimize.py -q
```

## E. 不测 / 弱测

方法卡质量、关系图谱业务正确性、工作区完整 AI 闭环、验证 Tab、任务看板、代训实跑。

## 结果

见同目录 [`2026-07-22-agent-acceptance-results.md`](2026-07-22-agent-acceptance-results.md)。

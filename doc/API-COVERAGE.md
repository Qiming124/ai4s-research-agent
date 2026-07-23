# API 覆盖清单

> **67** 个业务 REST 端点（`/health` + `/v1/*`）· **15** 域 · 更新于 **v2.2**（以 `GET /openapi.json` 为准）  
> OpenAPI 另含生产静态入口 `GET /`（不计入上表）。  
> **调用链路详解**：[`API-ROUTES.md`](API-ROUTES.md)

图例：**UI** = 前端已接线 · **Test** = pytest/smoke · **Auto** = 自动化等级 (A=全自动/H=半自动/M=手动)

> 表中 `{id}` / `{path}` 为简写；代码参数名见 API-ROUTES。

| 域 | 方法 | 路径 | UI | Test | Auto | 说明 |
|----|------|------|:--:|:----:|:----:|------|
| Health | GET | `/health` | ✓ | ✓ | A | 后端存活检测 |
| Chat | POST | `/v1/chat` | — | ✓ | H | 非流式，脚本/测试用 |
| Chat | POST | `/v1/chat/stream` | ✓ | ✓ | A | SSE 主对话；带 `project_id` 时自动 link 会话 |
| Sessions | GET | `/v1/sessions` | ✓ | ✓ | A | 会话列表 |
| Sessions | GET | `/v1/sessions/{id}` | ✓ | ✓ | A | 历史恢复 |
| Sessions | DELETE | `/v1/sessions/{id}` | ✓ | ✓ | H | 清空/删除 |
| Agents | GET | `/v1/agents` | ✓ | ✓ | A | 动态 Agent 列表 |
| MCP | GET | `/v1/mcp/status` | ✓ | ✓ | A | MCP 状态 |
| MCP | POST | `/v1/mcp/reload` | ✓ | ✓ | H | 热重载配置 |
| Documents | POST | `/v1/documents` | ✓ | ✓ | H | 文本入库 |
| Documents | POST | `/v1/documents/upload` | ✓ | ✓ | H | PDF/DOCX/MD 上传 |
| Documents | POST | `/v1/documents/from-arxiv` | ✓ | ✓ | H | arXiv 导入 |
| Documents | GET | `/v1/documents` | ✓ | ✓ | A | 列表 |
| Documents | DELETE | `/v1/documents` | — | ✓ | M | 全局 purge |
| Documents | DELETE | `/v1/documents/session/{id}` | ✓ | ✓ | H | 清空会话文档 |
| Documents | DELETE | `/v1/documents/{doc_id}` | ✓ | ✓ | H | 删除单条 |
| Documents | GET | `/v1/sessions/{id}/rag-refs` | ✓ | ✓ | A | RAG 引用 |
| Memory | GET | `/v1/memory/structured` | ✓ | ✓ | A | 定理库 |
| Memory | GET | `/v1/memory/structured/global` | ✓ | ✓ | A | 全局记忆 |
| Memory | POST | `/v1/memory/structured` | — | ✓ | A | Agent / 手工写入 |
| Memory | PATCH | `/v1/memory/structured/{id}` | ✓ | ✓ | A | 更新条目 |
| Memory | DELETE | `/v1/memory/structured/{id}` | ✓ | ✓ | A | 删除条目 |
| Memory | POST | `/v1/memory/structured/preview-markdown` | ✓ | ✓ | A | Markdown 导入预览 |
| Memory | POST | `/v1/memory/structured/import-preview` | ✓ | ✓ | A | PDF 等导入预览 |
| Memory | GET | `/v1/memory/structured/{id}/versions` | — | ✓ | H | L4 版本列表 |
| Memory | POST | `/v1/memory/structured/{id}/versions` | — | ✓ | H | L4 新建版本 |
| Memory | POST | `/v1/memory/structured/{id}/edges` | — | ✓ | H | 图谱边 |
| Projects | GET | `/v1/projects` | ✓ | ✓ | A | 课题列表 |
| Projects | POST | `/v1/projects` | ✓ | ✓ | H | 新建课题 |
| Projects | GET | `/v1/projects/{id}` | ✓ | ✓ | A | 课题详情 |
| Projects | PATCH | `/v1/projects/{id}` | ✓ | ✓ | H | 更新课题 |
| Projects | DELETE | `/v1/projects/{id}` | ✓ | ✓ | H | 删除课题（可 purge） |
| Projects | GET | `/v1/projects/{id}/members` | ✓ | ✓ | A | 成员 |
| Projects | GET | `/v1/projects/{id}/sessions` | ✓ | ✓ | A | 关联会话（存活） |
| Projects | GET | `/v1/projects/{id}/tasks` | ✓ | ✓ | A | 任务看板 |
| Projects | POST | `/v1/projects/{id}/tasks` | ✓ | ✓ | H | 新建任务 |
| Projects | PATCH | `/v1/projects/{id}/tasks/{tid}` | ✓ | ✓ | H | 更新状态 |
| Projects | POST | `/v1/projects/{id}/sessions/{sid}` | ✓ | ✓ | A | 关联会话 |
| Projects | DELETE | `/v1/projects/{id}/sessions/{sid}` | — | ✓ | H | 取消关联 |
| Artifacts | GET | `/v1/artifacts` | ✓ | ✓ | A | 列出工件 |
| Artifacts | GET | `/v1/artifacts/{id}` | ✓ | ✓ | H | 单条工件 |
| Artifacts | POST | `/v1/artifacts` | — | ✓ | H | 写入工件 |
| Artifacts | PATCH | `/v1/artifacts/{id}` | ✓ | ✓ | A | 更新工件 |
| Artifacts | DELETE | `/v1/artifacts/{id}` | ✓ | ✓ | A | 删除工件 |
| Verification | GET | `/v1/verification/dashboard` | ✓ | ✓ | A | 验证仪表盘 |
| Verification | GET | `/v1/verification/records` | ✓ | ✓ | A | 验证账本 |
| Verification | POST | `/v1/verification/run` | ✓ | ✓ | H | 手动验证 |
| Experiments | GET | `/v1/experiments/runs` | ✓ | ✓ | A | 实验列表（按 project_id） |
| Experiments | GET | `/v1/experiments/runs/{id}` | ✓ | ✓ | H | 实验详情 |
| Experiments | PATCH | `/v1/experiments/runs/{id}` | ✓ | ✓ | H | 更新 name/summary/metrics/status |
| Experiments | DELETE | `/v1/experiments/runs/{id}` | ✓ | ✓ | H | 删除实验记录 |
| Experiments | POST | `/v1/experiments/runs` | ✓ | ✓ | H | 触发实验 |
| Export | GET | `/v1/export/preview` | ✓ | ✓ | A | 导出预览 Markdown |
| Export | POST | `/v1/export/polish` | ✓ | ✓ | H | LLM 润色草稿 |
| Export | POST | `/v1/export/md` | ✓ | ✓ | H | Markdown |
| Export | POST | `/v1/export/latex` | ✓ | ✓ | H | LaTeX |
| Export | POST | `/v1/export/docx` | ✓ | ✓ | H | Word |
| Export | POST | `/v1/export/pdf` | ✓ | ✓ | H | PDF |
| Prompt | GET | `/v1/prompt/templates` | ✓ | ✓ | A | 润色风格模板 |
| Prompt | GET | `/v1/prompt/test-cases` | ✓ | ✓ | A | 提示词测试案例 |
| Prompt | POST | `/v1/prompt/optimize` | ✓ | ✓ | H | AI 润色优化 |
| Stats | GET | `/v1/stats/tokens` | ✓ | ✓ | A | Token 统计 |
| Observability | GET | `/v1/observability/summary` | ✓ | ✓ | A | 可观测摘要 |
| Observability | GET | `/v1/observability/agent-quality` | ✓ | ✓ | A | Agent 质量 |
| Sync | GET | `/v1/sync/audit/{id}` | — | ✓ | M | 课题审计日志 |
| Jupyter | POST | `/v1/jupyter/upload-result` | ✓ | ✓ | H | JSON 回传 → DataPacket |
| Jupyter | POST | `/v1/jupyter/upload-file` | ✓ | ✓ | H | 多格式回传 |

## 已移除（勿再测）

| 原路径 | 说明 |
|--------|------|
| `/v1/projects/.../campaign*` | Campaign S0–S8 整包删除 |
| `/v1/bibliography*` | 书目 HTTP 移除；LaTeX 仍可内部用 `bibliography.py` |
| `/v1/theory/workspace*` · `/v1/theory/assumption-dag*` · `/v1/theory/symbols` | Theory HTTP 与速览移除；种子仍注入 prompt |
| `GET /v1/memory/structured/graph` | 关系图谱视图移除；边 CRUD 保留 |
| `POST /v1/sync/metadata` | 云同步元数据移除 |
| `GET /v1/prompt/test-cases/{case_id}` | 单案例端点移除 |

## 全链路黄金路径

```
课题选择 → 新建会话(自动关联) → 文献导入(arXiv/PDF) → 对话(SSE / 场景工作流)
  → Artifact（推导迹 / 实验计划 / 下一步）→ 导出 preview/polish → LaTeX/DOCX/PDF/MD
```

## 测试入口

- `pytest tests/unit/` · `pytest tests/test_*.py` — 单元与模块回归
- `pytest tests/e2e/` — 黄金路径 workflow
- `cd app/web && npx playwright test` — 浏览器 E2E（课题 / 文献 / 导出）

字段与 SSE 细节见 [`API.md`](API.md)；**全路径链路**见 [`API-ROUTES.md`](API-ROUTES.md)；OpenAPI：`GET /docs`。

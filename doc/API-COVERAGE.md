# API 覆盖清单

> **67** 个 REST 端点 · **15** 域 · 更新于 **v2.2**（`app/server/api/*.py`）

图例：**UI** = 前端已接线 · **Test** = pytest/smoke · **Auto** = 自动化等级 (A=全自动/H=半自动/M=手动)

| 域 | 方法 | 路径 | UI | Test | Auto | 说明 |
|----|------|------|:--:|:----:|:----:|------|
| Health | GET | `/health` | ✓ | ✓ | A | 后端存活检测 |
| Chat | POST | `/v1/chat` | — | ✓ | H | 非流式，脚本/测试用 |
| Chat | POST | `/v1/chat/stream` | ✓ | ✓ | A | SSE 主对话 |
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
| Memory | GET | `/v1/memory/structured/graph` | ✓ | ✓ | A | 知识图谱 |
| Memory | POST | `/v1/memory/structured` | — | ✓ | A | Agent 写入 |
| Memory | GET | `/v1/memory/structured/{id}/versions` | — | ✓ | H | L4 版本列表 |
| Memory | POST | `/v1/memory/structured/{id}/versions` | — | ✓ | H | L4 新建版本 |
| Memory | POST | `/v1/memory/structured/{id}/edges` | — | ✓ | H | 图谱边 |
| Theory | GET | `/v1/theory/workspace` | ✓ | ✓ | A | 工作区列表 |
| Theory | GET | `/v1/theory/workspace/{path}` | ✓ | ✓ | A | 读文件 |
| Theory | PUT | `/v1/theory/workspace/{path}` | ✓ | ✓ | H | 写文件 |
| Theory | GET | `/v1/theory/assumption-matrix` | ✓ | ✓ | A | 假设矩阵 |
| Theory | GET | `/v1/theory/symbols` | ✓ | ✓ | A | 符号表 |
| Theory | GET | `/v1/theory/assumptions` | ✓ | ✓ | A | 假设列表 |
| Theory | GET | `/v1/theory/assumption-dag` | ✓ | ✓ | A | 假设 DAG |
| Theory | GET | `/v1/theory/assumption-dag/impact/{id}` | ✓ | ✓ | H | 影响传播 |
| Theory | GET | `/v1/bibliography` | ✓ | ✓ | A | 书目 |
| Theory | GET | `/v1/bibliography/export.bib` | ✓ | ✓ | H | BibTeX |
| Projects | GET | `/v1/projects` | ✓ | ✓ | A | 课题列表 |
| Projects | POST | `/v1/projects` | ✓ | ✓ | H | 新建课题 |
| Projects | GET | `/v1/projects/{id}` | ✓ | ✓ | A | 课题详情 |
| Projects | GET | `/v1/projects/{id}/members` | ✓ | ✓ | A | 成员 |
| Projects | GET | `/v1/projects/{id}/sessions` | ✓ | ✓ | A | 关联会话 |
| Projects | GET | `/v1/projects/{id}/tasks` | ✓ | ✓ | A | 任务看板 |
| Projects | POST | `/v1/projects/{id}/tasks` | ✓ | ✓ | H | 新建任务 |
| Projects | PATCH | `/v1/projects/{id}/tasks/{tid}` | ✓ | ✓ | H | 更新状态 |
| Projects | POST | `/v1/projects/{id}/sessions/{sid}` | ✓ | ✓ | A | 关联会话 |
| Campaigns | GET | `/v1/projects/{id}/campaign` | ✓ | ✓ | A | 当前活跃 Campaign |
| Campaigns | GET | `/v1/projects/{id}/campaigns` | ✓ | ✓ | A | Campaign 列表 |
| Campaigns | POST | `/v1/projects/{id}/campaign` | ✓ | ✓ | H | 创建/启动 Campaign |
| Campaigns | GET | `/v1/projects/{id}/campaigns/{cid}` | ✓ | ✓ | A | Campaign 详情 |
| Campaigns | PATCH | `/v1/projects/{id}/campaigns/{cid}` | ✓ | ✓ | H | 更新阶段/状态 |
| Verification | GET | `/v1/verification/dashboard` | ✓ | ✓ | A | 验证仪表盘 |
| Verification | GET | `/v1/verification/records` | ✓ | ✓ | A | 验证账本 |
| Verification | POST | `/v1/verification/run` | ✓ | ✓ | H | 手动验证 |
| Experiments | GET | `/v1/experiments/runs` | ✓ | ✓ | A | 实验列表 |
| Experiments | GET | `/v1/experiments/runs/{id}` | ✓ | ✓ | H | 实验详情 |
| Experiments | POST | `/v1/experiments/runs` | ✓ | ✓ | H | 触发实验 |
| Export | GET | `/v1/export/preview` | ✓ | ✓ | A | 导出预览 Markdown |
| Export | POST | `/v1/export/polish` | ✓ | ✓ | H | LLM 润色草稿 |
| Export | POST | `/v1/export/md` | ✓ | ✓ | H | Markdown |
| Export | POST | `/v1/export/latex` | ✓ | ✓ | H | LaTeX |
| Export | POST | `/v1/export/docx` | ✓ | ✓ | H | Word |
| Export | POST | `/v1/export/pdf` | ✓ | ✓ | H | PDF |
| Stats | GET | `/v1/stats/tokens` | ✓ | ✓ | A | Token 统计 |
| Observability | GET | `/v1/observability/summary` | ✓ | ✓ | A | 可观测摘要 |
| Observability | GET | `/v1/observability/agent-quality` | ✓ | ✓ | A | Agent 质量 |
| Sync | POST | `/v1/sync/metadata` | — | ✓ | M | 云端元数据同步（需 `ENABLE_CLOUD_SYNC`） |
| Sync | GET | `/v1/sync/audit/{id}` | — | ✓ | M | 审计日志 |
| Jupyter | GET | `/v1/jupyter/template` | ✓ | ✓ | H | 笔记本模板 |
| Jupyter | POST | `/v1/jupyter/upload-result` | ✓ | ✓ | H | 回传结果 |

## 全链路黄金路径

```
课题选择 → 新建会话(自动关联) → 文献导入(arXiv/PDF) → 对话(SSE流水线)
  → 自动切Tab → Campaign 阶段推进(可选) → 验证仪表盘刷新
  → 导出 preview/polish → LaTeX/DOCX/PDF/MD(按课题)
```

## 测试入口

- `pytest tests/api/` — 分域 API 测试
- `pytest tests/e2e/` — 黄金路径 workflow
- `pytest tests/api/test_smoke_all.py` — 全量冒烟（CI）
- `cd app/web && npx playwright test` — 浏览器 E2E（课题 / 文献 / 导出）

字段与 SSE 细节见 [`API.md`](API.md)；OpenAPI：`GET /docs`。

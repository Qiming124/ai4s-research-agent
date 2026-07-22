# API 参考（v2.2）

Base URL 默认：`http://127.0.0.1:8000`。  
数据模型：`app/shared/schemas.py`。  
**完整端点矩阵（71）**：[`API-COVERAGE.md`](API-COVERAGE.md)。  
**全路径调用链路**：[`API-ROUTES.md`](API-ROUTES.md)。  
交互式文档：`GET /docs`。

---

## 健康检查

### `GET /health`

返回 `HealthResponse`：`status`、`model`、`reasoning_effort`。

```bash
curl -s http://127.0.0.1:8000/health
```

---

## 对话

### `POST /v1/chat` / `POST /v1/chat/stream`

非流式返回完整 JSON；流式为 `Content-Type: text/event-stream`。

**请求体** `ChatRequest`（常用字段）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `message` | string | 用户输入（必填） |
| `session_id` | string? | 会话 ID，空则服务端生成 |
| `mode` | `chat` \| `math` | 对话模式 |
| `system_prompt` | string? | 覆盖默认 system prompt |
| `max_history_messages` | int? | L1 历史条数，null 用服务端默认 |
| `enable_history_summary` | bool? | 是否摘要旧历史 |
| `enable_tools` | bool? | 是否启用 MCP，null 用 `ENABLE_MCP` |
| `agent` | string? | `general` / `theory` / `experiment` / `literature` / `review` / `counterexample` |
| `auto_route` | bool | 是否自动路由（默认 true） |
| `enable_thinking` | bool? | DeepSeek thinking |
| `reasoning_effort` | `high` \| `max`? | 推理强度 |
| `cot_mode` | `off` \| `standard` \| `strict` | 结构化思维链（Math 默认 strict） |
| `project_id` | string? | 关联课题（工作台 / 理论工作区 / Artifact 上下文） |

**SSE 事件 `type`**：

| type | 说明 |
|------|------|
| `meta` | 会话 ID、agent_name、route_reason |
| `reasoning` / `content` | 思考 / 正文片段 |
| `tool_call_start` / `tool_call_result` / `tool_call_error` | MCP 工具 |
| `agent_handoff` | 多 Agent 切换 |
| `workflow_step` | 规划/工具/验证/综合 |
| `cot_step` | 结构化思维链小节 |
| `verification_result` / `numerical_verification_result` | 符号 / 数值验证 |
| `pipeline_stage` | 遗留兼容名（主路径用 `workflow_step`） |
| `artifact_saved` | Artifact 落盘（方法卡、实验计划等） |
| `memory_warning` | L4 矛盾告警 |
| `done` / `error` | 结束 / 错误 |

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"二次损失临界点","session_id":"demo","mode":"math","agent":"theory"}'
```

---

## 会话

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/sessions` | 会话列表 |
| GET | `/v1/sessions/{id}` | 历史（含 reasoning、tool_calls、workflow_steps） |
| DELETE | `/v1/sessions/{id}` | 清空会话 |

---

## 课题 / 任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/v1/projects` | 列表 / 新建 |
| GET | `/v1/projects/{id}` | 详情 |
| PATCH | `/v1/projects/{id}` | 更新名称/简介 |
| DELETE | `/v1/projects/{id}?purge=true` | 整包删除（会话+工作区；`default` 不可删） |
| GET | `/v1/projects/{id}/members` | 成员（角色） |
| GET/POST | `/v1/projects/{id}/tasks` | 任务看板 |
| PATCH | `/v1/projects/{id}/tasks/{tid}` | 更新任务状态 |
| GET/POST/DELETE | `/v1/projects/{id}/sessions…` | 课题-会话关联 / 取消关联 |

场景工作流（`RESEARCH_PIPELINE_MODE=auto`）：`lit_to_theory` / `experiment_plan` / `data_to_nextstep`。Campaign S0–S8 已移除。

---

## 验证账本

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/verification/dashboard` | 仪表盘汇总 |
| GET | `/v1/verification/records` | 记录列表 |
| POST | `/v1/verification/run` | 手动重跑验证 |

---

## MCP / Agents / 可观测

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/mcp/status` | MCP 连接与工具列表 |
| POST | `/v1/mcp/reload` | 热重载 MCP 配置 |
| GET | `/v1/agents` | 编排后端与各 Agent 元数据 |
| GET | `/v1/observability/summary` | 请求/错误摘要 |
| GET | `/v1/observability/agent-quality` | Agent 质量面板 |
| GET | `/v1/stats/tokens` | Token 用量（需 `ENABLE_TOKEN_STATS`） |

---

## RAG 文档

需 `ENABLE_RAG=true`。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/documents` | 文本入库 |
| POST | `/v1/documents/upload` | PDF/DOCX/MD |
| POST | `/v1/documents/from-arxiv` | arXiv 入库 |
| GET | `/v1/documents` | 列表 |
| DELETE | `/v1/documents` | 全局 purge |
| DELETE | `/v1/documents/session/{id}` | 按会话清空 |
| DELETE | `/v1/documents/{doc_id}` | 删除单条 |
| GET | `/v1/sessions/{id}/rag-refs` | 检索引用 |

---

## L4 结构化记忆与理论工作区

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/v1/memory/structured` | 定理库列表 / 写入 |
| PATCH/DELETE | `/v1/memory/structured/{id}` | 更新 / 删除条目（删边级联） |
| POST | `/v1/memory/structured/preview-markdown` | Markdown 导入预览（不写库） |
| POST | `/v1/memory/structured/import-preview` | PDF/DOCX/MD 导入预览（LLM 候选，不写库） |
| GET | `/v1/memory/structured/global` | 全局引理 |
| GET | `/v1/memory/structured/graph` | 知识图谱 |
| GET/POST | `/v1/memory/structured/{id}/versions` | 版本 |
| POST | `/v1/memory/structured/{id}/edges` | 依赖边 |
| GET/POST | `/v1/artifacts` | 课题工件列表 / 手动创建 |
| GET/PATCH/DELETE | `/v1/artifacts/{id}` | 工件详情 / 更新 / 删除 |
| GET | `/v1/theory/workspace` | 文件列表 |
| GET/PUT | `/v1/theory/workspace/{path}` | 读写（含 symbols/assumptions.md） |
| GET | `/v1/theory/assumption-dag` (+ `/impact/{id}`) | 假设 DAG |

---

## 实验 / 导出 / Jupyter / 同步

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/v1/experiments/runs` | 列表 / 触发 |
| GET | `/v1/experiments/runs/{id}` | 详情 |
| GET | `/v1/export/preview` | 预览草稿（`session_id` / `include_global` / `include_chat`；**无** `project_id`） |
| POST | `/v1/prompt/optimize` | AI 多风格优化提示词（RCCF/IMRaD 等） |
| GET | `/v1/prompt/templates` | 提示词风格模板（`conf/prompt/templates.json`） |
| GET | `/v1/prompt/test-cases` | 科研测试案例全文列表（`conf/prompt/test_cases.json`） |
| POST | `/v1/export/{md,latex,docx,pdf}` | 导出文件 |
| POST | `/v1/jupyter/upload-result` | 结果回传（JSON body：summary + metrics） |
| POST | `/v1/jupyter/upload-file` | 多格式文件回传（`.json` / `.csv` / `.tsv` / `.xlsx`，multipart） |
| GET | `/v1/sync/audit/{project_id}` | 课题审计日志 |

导出正文按 **session + 全局记忆** 收集（`collect_export_entries`）。`LatexExportRequest.project_id` 主要用于 **LaTeX/BibTeX 书目**；preview/md/docx/pdf **不会**按课题过滤正文。无 xelatex 时 PDF 走 HTML→reportlab 回退。全链路见 [`API-ROUTES.md`](API-ROUTES.md#8-export)。

---

## 错误码

| 状态码 | 含义 |
|--------|------|
| 422 | 请求体校验失败 |
| 403 | 同步未启用 / 路径越界等 |
| 404 | 资源不存在 |
| 502 | LLM / 上游调用失败 |

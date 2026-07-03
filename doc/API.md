# API 参考

Base URL 默认：`http://127.0.0.1:8000`。  
数据模型详见 `shared/schemas.py`。

## 健康检查

### `GET /health`

**返回** `HealthResponse`：`status`、`model`、`reasoning_effort`。

```bash
curl -s http://127.0.0.1:8000/health
```

---

## 对话

### `POST /v1/chat`

非流式对话，一次返回完整 JSON。

**请求体** `ChatRequest`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `message` | string | 用户输入（必填） |
| `session_id` | string? | 会话 ID，空则服务端生成 |
| `mode` | `chat` \| `math` | 对话模式 |
| `system_prompt` | string? | 覆盖默认 system prompt |
| `max_history_messages` | int? | L1 历史条数，null 用服务端默认 |
| `enable_history_summary` | bool? | 是否摘要旧历史 |
| `enable_tools` | bool? | 是否启用 MCP，null 用 `ENABLE_MCP` |
| `agent` | string? | `general` / `theory` / `experiment` / `literature` / `review` |
| `auto_route` | bool | 是否自动路由（默认 true） |
| `enable_thinking` | bool? | 是否启用 DeepSeek thinking（null=默认开启，仅最终回答） |
| `reasoning_effort` | `high` \| `max`? | 推理强度，null 用 `REASONING_EFFORT` |
| `cot_mode` | `off` \| `standard` \| `strict` | 结构化思维链（Math 模式默认 strict） |

**返回** `ChatResponse`：`session_id`、`content`、`reasoning`、`usage`。

### `POST /v1/chat/stream`

SSE 流式对话，`Content-Type: text/event-stream`。

**SSE 事件 `type`**：

| type | 说明 |
|------|------|
| `meta` | 会话 ID、agent_name、route_reason |
| `reasoning` | 思考过程片段 |
| `content` | 回答正文片段 |
| `tool_call_start` | 工具开始，`tool_name`、`tool_call_id` |
| `tool_call_result` | 工具成功结果 |
| `tool_call_error` | 工具失败 |
| `agent_handoff` | 多 Agent 切换，`from_agent`、`to_agent` |
| `workflow_step` | 工作流节点：`step_kind`（plan/tool/verify/synthesize）、`status`、`title` |
| `cot_step` | 结构化思维链小节（JSON：`step`、`title`、`body`） |
| `verification_result` | Theory SymPy 验证结果（JSON） |
| `numerical_verification_result` | 数值验证 fallback 结果（JSON） |
| `pipeline_stage` | 多跳研究流水线阶段名（如 `theory_derivation`） |
| `memory_warning` | L4 矛盾检测告警文本 |
| `done` | 结束，含 `usage` |
| `error` | 错误信息 |

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"你好","session_id":"demo"}'
```

---

## 会话

### `GET /v1/sessions/{session_id}`

返回 `SessionResponse`：历史消息列表（含 `reasoning_content`、`tool_calls`、`workflow_steps`）。

### `DELETE /v1/sessions/{session_id}`

清空该会话消息，返回 `{"status":"cleared","session_id":"..."}`。

---

## MCP

### `GET /v1/mcp/status`

返回 `MCPStatusResponse`：

- `server_enabled`：服务端 `ENABLE_MCP`
- `connected`：Client 是否已连接
- `servers[]`：各 Server 名称、连接状态、工具列表

---

## RAG 文档

需 `ENABLE_RAG=true`。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/documents` | 上传文本/Markdown 索引 |
| POST | `/v1/documents/upload` | multipart 上传 PDF 或文本文件 |
| POST | `/v1/documents/from-arxiv` | 从 arXiv 下载 PDF 并入库（`?session_id=&arxiv_id=`） |
| GET | `/v1/documents` | 列出已索引文档（`?session_id=`） |
| DELETE | `/v1/documents/{doc_id}` | 删除文档及向量 |
| GET | `/v1/sessions/{id}/rag-refs` | 会话检索引用记录 |

---

## L4 结构化记忆与知识图谱

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/memory/structured` | 列出定理/引理（`?session_id=&kind=`） |
| GET | `/v1/memory/structured/global` | 全局引理库（`session_id IS NULL`） |
| GET | `/v1/memory/structured/graph` | 知识图谱节点 + 边 |
| POST | `/v1/memory/structured` | 手动创建条目 |
| POST | `/v1/memory/structured/{id}/edges` | 创建依赖边（`depends_on` 等） |

---

## 理论工作区

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/theory/workspace` | 列出 `data/theory/` 文件 |
| GET | `/v1/theory/workspace/{path}` | 读取工作区文件正文 |
| GET | `/v1/theory/symbols` | 符号表 Markdown |
| GET | `/v1/theory/assumptions` | 全局假设 Markdown |
| GET | `/v1/theory/assumption-matrix` | 假设-定理对照矩阵 |

---

## 实验日志

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/experiments/runs` | 列出 `data/experiments/logs/*.json` |
| GET | `/v1/experiments/runs/{run_id}` | 单条实验运行详情 |

---

## 导出

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/export/latex` | 从 L4 记忆生成 LaTeX（写入 `data/theory/proofs/export.tex`） |

---

## Agent 元数据

### `GET /v1/agents`

返回 `orchestration_backend` 与各 Agent 的 `description`、`rag_enabled`、`default_tool_patterns`。

---

## Token 统计

需 `ENABLE_TOKEN_STATS=true`。

### `GET /v1/stats/tokens`

查询参数（均可选）：`session_id`、`agent_name`、`day`（YYYY-MM-DD）。

返回各 Agent 与合计 token 用量。

---

## 错误码

| 状态码 | 含义 |
|--------|------|
| 422 | 请求体校验失败 |
| 404 | 会话或文档不存在 |
| 502 | LLM / 上游调用失败 |

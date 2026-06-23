# 架构说明

## 分层结构

```
┌─────────────────────────────────────────┐
│  传输层：CLI / Web（SSE 客户端）          │
├─────────────────────────────────────────┤
│  API：server/api/*.py（FastAPI 路由）    │
├─────────────────────────────────────────┤
│  Agent：GeneralAgent / MultiAgent 编排   │
├──────────────┬──────────────────────────┤
│  记忆 L1/L2/L3 │  LLM + LangChain 适配   │
├──────────────┴──────────────────────────┤
│  MCP 工具层 / 可观测性 / 配置            │
└─────────────────────────────────────────┘
```

## 一次流式对话链路

1. Web/CLI → `POST /v1/chat/stream`
2. `chat.py` 校验 `ChatRequest`，选择 `legacy` 或 `langgraph` 编排
3. Agent 读取 L2 会话历史，经 L1 截断/摘要后拼消息
4. 若启用 MCP：工具循环调用 `MCPClient` → stdio Server
5. 若启用 RAG（指定 Agent）：检索 Chroma → 注入 system prompt
6. `DeepSeekClient` 或 LangChain `ChatOpenAI` 流式返回
7. `StreamChunk` 序列化为 SSE → 客户端渲染

## 记忆分层

| 层级 | 实现 | 说明 |
|------|------|------|
| L1 工作记忆 | `memory/working.py`、`manager.py` | 历史截断、可选摘要 |
| L2 会话 | `memory/session.py`、`sqlite_store.py` | session_id → 消息列表 |
| L3 RAG | `memory/rag/store.py` | Chroma 向量库，全局共享 |

## 编排后端

| `ORCHESTRATION_BACKEND` | 行为 |
|-------------------------|------|
| `legacy` | `GeneralAgent` + 自研 tool loop |
| `langgraph` | `MultiAgentOrchestrator` → theory / experiment / literature 子 Agent |

## MCP

- 配置：`conf/mcp_servers.json`
- 运行时：`MCPClient` 拉起 stdio 子进程（web_search、arxiv、filesystem）
- 工具名：`{server}__{tool}`，如 `filesystem__list_files`
- 详见 [mcp-config.md](mcp-config.md)

## Web 前端

- 开发：`app/web/` Vite + React，5173 代理 8000
- 生产：`npm run build` → `app/web/dist`，由 `server/main.py` 托管
- 状态：会话列表 localStorage；消息从 `GET /v1/sessions/{id}` 恢复

## 关键目录

| 路径 | 职责 |
|------|------|
| `app/shared/schemas.py` | 请求/响应模型 |
| `app/shared/paths.py` | 目录布局常量 |
| `app/server/config.py` | `conf/.env` → Settings |
| `app/server/agents/` | Agent 与编排 |
| `app/server/mcp/` | MCP Client、Registry、内置 Server |
| `app/server/graph/` | LangGraph ReAct 子图 |
| `app/server/memory/rag/` | RAG 入库与检索 |
| `app/server/observability/` | 结构化日志、token 统计 |
| `app/web/src/` | React UI |
| `conf/` | 环境变量模板与 MCP JSON |
| `log/` | 运行时日志 |

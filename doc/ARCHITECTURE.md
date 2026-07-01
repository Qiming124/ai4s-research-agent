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
6. 若 theory Agent：注入 L4 结构化记忆 → 推导 → SymPy 验证 → 自动持久化引理
7. `DeepSeekClient` 或 LangChain `ChatOpenAI` 流式返回
8. `StreamChunk` 序列化为 SSE → 客户端渲染

## 记忆分层

| 层级 | 实现 | 说明 |
|------|------|------|
| L1 工作记忆 | `memory/working.py`、`manager.py` | 历史截断、可选摘要 |
| L2 会话 | `memory/session.py`、`sqlite_store.py` | session_id → 消息列表 |
| L3 RAG | `memory/rag/store.py` | Chroma 向量库，全局共享 |
| L4 结构化记忆 | `memory/structured/store.py` | 定理/假设/引理 SQLite，可注入 theory prompt |

## Theory 推导闭环（v0.3）

```
mode=math / theory Agent
  → RAG 注入（symbols/assumptions）
  → L4 注入（已证引理）
  → LangGraph ReAct（SymPy / rag MCP）
  → verification_result（SymPy 自动验证）
  → 自动抽取 ## 引理/定理 → L4 持久化
```

- 分阶段 CoT prompt：`app/server/llm/prompts.py` → `THEORY_AGENT_PROMPT`
- 验证逻辑：`app/server/graph/theory_pipeline.py`
- 理论工作区：`data/theory/`（symbols、assumptions、workflows）

## 编排后端

| `ORCHESTRATION_BACKEND` | 行为 |
|-------------------------|------|
| `legacy` | `GeneralAgent` + 自研 tool loop |
| `langgraph` | `MultiAgentOrchestrator` → theory / experiment / literature 子 Agent |

## MCP

- 配置：`conf/mcp_servers.json`
- 运行时：`MCPClient` 拉起 stdio 子进程（web_search、arxiv、filesystem、sympy、rag）
- 工具名：`{server}__{tool}`，如 `filesystem__list_files`
- 详见 [mcp-config.md](mcp-config.md)

## Web 前端

- 开发：`app/web/` Vite + React，5173 代理 8000
- 生产：`npm run build` → `app/web/dist`，由 `app/server/main.py` 托管
- 状态：会话列表 localStorage；消息从 `GET /v1/sessions/{id}` 恢复

## 关键目录

| 路径 | 职责 |
|------|------|
| `app/shared/schemas.py` | 请求/响应模型 |
| `app/shared/paths.py` | 目录布局常量 |
| `app/server/config.py` | `conf/.env` → Settings |
| `app/server/agents/` | Agent 与编排 |
| `app/server/mcp/` | MCP Client、Registry、内置 Server |
| `app/server/graph/` | LangGraph ReAct 子图、theory 验证 |
| `app/server/memory/rag/` | RAG 入库与检索 |
| `app/server/memory/structured/` | L4 结构化记忆与注入 |
| `app/server/observability/` | 结构化日志、token 统计 |
| `app/web/src/` | React UI |
| `conf/` | 环境变量模板与 MCP JSON |
| `data/` | 会话 DB、Chroma、MCP 文件、**theory 工作区** |

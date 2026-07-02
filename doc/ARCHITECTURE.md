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

## Theory 推导闭环（v0.4）

```
mode=math / theory Agent
  → 理论工作区注入（data/theory/symbols.md、assumptions.md）
  → L4 知识图谱注入（引理/假设 + memory_edges）
  → LangGraph ReAct（SymPy + numerical + rag MCP）
  → verification_result（SymPy）+ numerical_verification_result（fallback）
  → 自动抽取 ## 引理/定理 → L4 + 矛盾检测 memory_warning
```

## 研究流水线（RESEARCH_PIPELINE_MODE=auto）

`app/server/graph/research_pipeline.py`：

literature → theory → experiment（条件） → review

## Agent 角色（v0.4）

| Agent | 职责 |
|-------|------|
| general | 通用问答 |
| theory | 数学推导 + 双验证 |
| experiment | 数值实验 + numerical MCP |
| literature | 文献检索 + PDF/arXiv 入库 |
| review | 审稿清单检查 |

## MCP（v0.4）

内置 Server：web_search、arxiv、filesystem、sympy、rag、**numerical**

## 新增 API

| 端点 | 说明 |
|------|------|
| `GET /v1/memory/structured/graph` | 知识图谱 |
| `GET /v1/theory/workspace` | 理论工作区文件列表 |
| `GET /v1/experiments/runs` | 实验日志 |
| `POST /v1/documents/upload` | PDF 上传 |
| `POST /v1/documents/from-arxiv` | arXiv 入库 |
| `POST /v1/export/latex` | LaTeX 导出 |

## Web 科研工作台（v0.4）

右栏：定理库、知识图谱、实验日志、理论工作区、LossLandscapeViz（消息内嵌）

## 编排后端

| `ORCHESTRATION_BACKEND` | 行为 |
|-------------------------|------|
| `legacy` | `GeneralAgent` + 自研 tool loop |
| `langgraph` | `MultiAgentOrchestrator` → 五 Agent + 可选 ResearchPipeline |

## MCP 配置

- 配置：`conf/mcp_servers.json`
- 运行时：`MCPClient` 拉起 stdio 子进程
- 详见 [mcp-config.md](mcp-config.md)

## Web 前端

- 开发：`app/web/` Vite + React，5173 代理 8000
- 生产：`npm run build` → `app/web/dist`，由 `app/server/main.py` 托管

## 关键目录

| 路径 | 职责 |
|------|------|
| `data/theory/` | 符号表、假设、引理、反例 |
| `data/experiments/` | 配置、日志、notebook |
| `app/server/experiments/` | 实验 runner |
| `app/server/memory/theory_workspace.py` | 工作区加载与注入 |
| `app/server/memory/structured/graph.py` | L4 知识图谱 |
| `app/server/graph/research_pipeline.py` | 多跳研究流水线 |

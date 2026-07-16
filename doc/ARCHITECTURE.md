# 架构说明（v2.2）

全景图见 [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)。端点清单见 [`API-COVERAGE.md`](API-COVERAGE.md)。

## 分层结构

```
┌─────────────────────────────────────────┐
│  传输层：CLI / Web（SSE 客户端）          │
├─────────────────────────────────────────┤
│  API：server/api/*.py（15 域 · 67 端点） │
├─────────────────────────────────────────┤
│  Agent：legacy General / LangGraph 多 Agent │
│         + ResearchPipeline / Campaign Supervisor │
├──────────────┬──────────────────────────┤
│  记忆 L1–L4 / 课题 / Campaign / 验证账本 │  LLM + MCP │
├──────────────┴──────────────────────────┤
│  可观测性 / 导出 / Jupyter / 可选云同步   │
└─────────────────────────────────────────┘
```

## 一次流式对话链路

1. Web/CLI → `POST /v1/chat/stream`（可带 `project_id` / `campaign_id`）
2. `chat.py` 校验 `ChatRequest`，选择 `legacy` 或 `langgraph` 编排
3. Agent 读 L2 历史，经 L1 截断/摘要后拼消息
4. MCP 启用时：工具循环 → stdio Server（按 Agent 白名单）
5. RAG 启用且 Agent 在 `RAG_AGENTS`：Chroma 检索注入
6. theory / review：注入理论工作区 + L4；SymPy → 可选 numerical
7. 流式 `StreamChunk` → SSE（含 `pipeline_stage` / `campaign_update` / 验证事件）
8. 验证账本 / L4 / Campaign 产物按需落盘

## 记忆与课题

| 层级 / 模块 | 实现 | 说明 |
|-------------|------|------|
| L1 工作记忆 | `memory/working.py` | 截断、可选摘要 |
| L2 会话 | `memory/session.py` | SQLite / 内存 |
| L3 RAG | `memory/rag/` | Chroma，按 session 隔离 |
| L4 结构化 | `memory/structured/` | 定理/引理/边/版本 |
| 课题 | `memory/projects.py` + `api/projects.py` | Project、任务看板、会话关联 |
| Campaign | `memory/campaigns.py` + `api/campaigns.py` | S0–S8 阶段产物 |
| 验证账本 | `api/verification.py` + experiments | Claim 三层验证记录 |
| 书目 | `memory/bibliography.py` | BibTeX 导出 |

## Theory / 验证闭环

```
mode=math / theory Agent
  → 注入 symbols.md / assumptions.md + L4
  → SymPy（verification_result）
  → 可选 numerical / Torch（numerical_verification_result / skipped）
  → 抽取引理 → L4 + memory_warning
  → 写入验证账本（可手动 /v1/verification/run 重跑）
```

## 研究流水线与 Campaign

| 模式 | 入口 | 行为 |
|------|------|------|
| 多跳流水线 | `RESEARCH_PIPELINE_MODE=auto` 或 `/research` | literature → theory → experiment → review |
| Campaign Supervisor | `graph/research_supervisor.py` + Campaign API | S0 立项 … S8 归档；SSE `campaign_update` |

## Agent 角色

| Agent | 职责 |
|-------|------|
| general | 通用问答与协调 |
| theory | 数学推导 + 符号/数值验证 |
| experiment | 数值实验、谱、landscape |
| literature | 检索与 PDF/arXiv 入库 |
| review | 审稿清单检查 |
| counterexample | 反例搜索与验证 |

## MCP

内置 Server：`web_search`、`arxiv`、`filesystem`、`sympy`、`rag`、`numerical`。  
配置：`conf/mcp_servers.json`；白名单：`conf/mcp_tool_whitelist.json`。详见 [`mcp-config.md`](mcp-config.md)。

## API 域一览

Chat / Sessions / Agents / MCP / Documents / Memory / Theory / Projects / **Campaigns** / Verification / Experiments / Export / Stats / Observability / Sync / Jupyter。

## 编排后端

| `ORCHESTRATION_BACKEND` | 行为 |
|-------------------------|------|
| `legacy` | `GeneralAgent` + 自研 tool loop |
| `langgraph` / `multi` | Supervisor + SubAgent（含上述六角色）+ 可选流水线 |

## Web

`app/web/`：课题中心、科研工作台 Tabs（文献/理论/验证/图谱/实验/导出）、Campaign 进度、可观测面板。详见 [`web.md`](web.md)。

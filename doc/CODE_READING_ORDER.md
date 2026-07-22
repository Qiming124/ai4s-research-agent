# 后端代码阅读顺序（跳过前端）

面向想通读源码的同学。前端 `app/web/` 本文不讲；Web 见 [`web.md`](web.md)。

建议：**先跟「一次请求」走通主路径**，再按域展开。每节给出「必读 / 选读」与文件作用。

---

## 0. 开读前（30 分钟）

| 顺序 | 读什么 | 为什么 |
|------|--------|--------|
| 1 | 根目录 [`../README.md`](../README.md) | 项目能干什么、怎么启动 |
| 2 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | 分层、全景图与一次对话链路 |
| 3 | [`ENV.md`](ENV.md) 前半 | 配置从哪来 |
| 4 | [`DATA.md`](DATA.md) | `data/` 种子 vs 运行时 |
| 5 | [`CODE_STYLE.md`](CODE_STYLE.md) | 中文注释约定 |

启动一遍后端（`uvicorn server.main:app --app-dir app`），打开 `/docs`，对照后面的 API 文件。

---

## 1. 入口与配置（第 1 天）

| 顺序 | 文件 | 必读要点 |
|------|------|----------|
| 1 | `app/server/main.py` | FastAPI 生命周期、路由挂载、静态托管 |
| 2 | `app/server/config.py` | `Settings` / `get_settings()`；所有开关从这里长出来 |
| 3 | `app/shared/paths.py` | `DATA_ROOT` 等路径常量 |
| 4 | `app/shared/schemas.py` | **先读** `ChatRequest`、`StreamChunk`、`ChatMessage`；其余按需 |

读完应能回答：一次 HTTP 请求从哪进、配置从哪读、SSE chunk 长什么样。

---

## 2. 一次流式对话主路径（第 2–3 天，最重要）

按调用顺序读：

```
POST /v1/chat/stream
  → api/chat.py
  → agents/orchestrator.py（或多 Agent）
  → agents/subagent.py / agents/base.py
  → llm/client.py 或 LangGraph ReAct
  → memory/working.py（拼历史）
  → mcp/client.py（若开工具）
  → SSE StreamChunk 回前端
```

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `app/server/api/chat.py` | 流式入口、参数透传、错误包装 |
| 2 | `app/server/agents/orchestrator.py` | 意图路由 → 子 Agent / 研究流水线 |
| 3 | `app/server/agents/config.py` | Agent 名与归一化 |
| 4 | `app/server/agents/subagent.py` | LangGraph 路径的 SubAgent |
| 5 | `app/server/agents/base.py` | Legacy GeneralAgent、工具循环、历史里 `reasoning_content` |
| 6 | `app/server/llm/client.py` | DeepSeek 调用；thinking / stream |
| 7 | `app/server/llm/reasoning_options.py` | 请求级 thinking 开关解析 |
| 8 | `app/server/llm/prompts.py` | 系统提示 |
| 9 | `app/server/memory/working.py` | 工作记忆：历史截断、摘要开关 |
| 10 | `app/server/memory/session.py` + `sqlite_store.py` | L2 会话持久化 |
| 11 | `app/server/memory/base.py` | SessionStore 接口 |

**选读（同一天或次日）：**

- `llm/cot_prompt.py` / `cot_parser.py` — CoT 模式
- `observability/token_usage.py` / `middleware.py` — Token 与请求日志

读完应能回答：消息如何进 LLM、工具如何插进对话、历史如何截断、thinking 为何会 400。

---

## 3. MCP 工具层（第 3–4 天）

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `app/server/mcp/config.py` | 从 JSON 加载 MCP Server |
| 2 | `app/server/mcp/client.py` | 连接、列工具、调用 |
| 3 | `app/server/mcp/whitelist.py` | 工具白名单 |
| 4 | `app/server/mcp/registry.py` | 注册表 |
| 5 | `app/server/mcp/truncation.py` | 工具结果截断 |
| 6 | `mcp/servers/*.py` | 各内置工具：`arxiv` / `web_search` / `filesystem` / `rag` / `sympy` / `numerical` |
| 7 | `app/server/api/mcp.py` | 状态与热加载 API |
| 8 | [`mcp-config.md`](mcp-config.md) | 配置说明 |

配合读：`graph/react.py` + `graph/streaming.py`（ReAct 子图与最终回答流）。

---

## 4. LangGraph / 场景工作流（第 4–5 天）

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `app/server/graph/state.py` | 图状态结构 |
| 2 | `app/server/graph/react.py` | ReAct：call_model ↔ tools |
| 3 | `app/server/graph/streaming.py` | 子图流式 → SSE；最终 thinking 回答 |
| 4 | `app/server/graph/router.py` / `router_llm.py` | 路由 |
| 5 | `app/server/graph/nodes.py` / `workflow.py` | 通用图节点 |
| 6 | `app/server/graph/scenes/` | **场景工作流**（`auto`）：匹配 + 执行 |
| 7 | `app/server/graph/theory_pipeline.py` | 理论侧流水线片段 |
| 8 | `app/server/artifacts/` | Artifact 抽取 / 清洗 / 存储 |

读完应能画出：单 Agent vs `RESEARCH_PIPELINE_MODE=auto` 场景短协作的分支。

---

## 5. 课题 / 任务 / 理论工作区（第 5–6 天）

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `app/server/memory/projects.py` | 课题 CRUD、工作区、**整包删除** |
| 2 | `app/server/api/projects.py` | HTTP：含 `DELETE ?purge=true`、会话关联/取消关联 |
| 3 | `app/server/memory/theory_workspace.py` | 课题理论目录与 prompt 注入（无 HTTP） |
| 4 | `app/server/api/artifacts.py` | Artifact HTTP |
| 5 | `app/server/api/structured_memory.py` | L4 定理库 HTTP |

数据落盘：`data/projects/{id}/`（见 DATA.md）。Campaign 目录与 API 已移除。

---

## 6. 记忆分层 L1–L4 与 RAG（第 6–7 天）

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `memory/working.py` | L1 工作记忆（已在主路径读过） |
| 2 | `memory/session.py` / `sqlite_store.py` | L2 会话 |
| 3 | `memory/structured/store.py` | L3/L4 定理库条目 |
| 4 | `memory/structured/extract.py` | 从回复抽取结构 |
| 5 | `memory/structured/injection.py` | 注入 system 上下文 |
| 6 | `memory/structured/graph.py` | L4 边/元数据辅助（图谱视图 HTTP 已下线） |
| 7 | `api/structured_memory.py` | 结构化记忆 API |
| 8 | `memory/rag/store.py` | 文档注册 + Chroma |
| 9 | `memory/rag/chunking.py` / `embeddings.py` | 切块与向量 |
| 10 | `memory/rag/retrieval.py` / `context.py` | 检索与拼上下文 |
| 11 | `memory/rag/pdf_ingest.py` / `doc_ingest.py` | 入库 |
| 12 | `memory/rag/session_refs.py` | 会话引用轨迹 |
| 13 | `api/documents.py` | 上传 / arXiv 导入 |

**注意（读源码时别被文案骗到）：**  
`memory/bibliography.py` 仍供 **LaTeX 导出**内部注入 BibTeX；**书目 HTTP API 与 Web 书目库面板均已移除**。符号/假设经磁盘种子与 `theory_workspace` 注入 prompt，**无** `/v1/theory/workspace*` / `assumption-dag*` HTTP。

---

## 7. 验证与实验（第 7–8 天）

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `memory/verification.py` / `claim_parser.py` | 验证账本与 claim 解析 |
| 2 | `api/verification.py` | 验证 API |
| 3 | `experiments/verification_executor.py` | 执行验证 |
| 4 | `experiments/runner.py` / `torch_runner.py` | 实验跑批（可选；非主卖点） |
| 5 | `api/experiments.py` / `jupyter.py` | HTTP；Jupyter 回传可写 DataPacket |

---

## 8. 导出（第 8 天）

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `api/export.py` | preview / polish / md / latex / docx / pdf |
| 2 | `export/builder.py` | 收集条目、拼 Markdown / LaTeX |
| 3 | `export/ai_polish.py` | 润色提示词与调用 |
| 4 | `export/docx_exporter.py` + `math_docx_prep.py` | Word 与公式预处理 |
| 5 | `export/pdf_exporter.py` + `html_pdf_renderer.py` | PDF 与公式 Unicode 规范化 |
| 6 | 其余 `export/*` | pandoc / reportlab / 字体 — 按需 |

对照 [`API-ROUTES.md`](API-ROUTES.md) 第 8 节。

---

## 9. 其余 API 与外围（穿插）

| 文件 | 说明 |
|------|------|
| `api/agents.py` | 可用 Agent 列表 |
| `api/stats.py` | Token 统计 |
| `api/observability.py` | 质量 / 可观测摘要 |
| `api/sync.py` | 课题审计日志（云同步 metadata 已移除） |
| `api/prompt.py` | 润色模板 / 案例 / optimize |
| `api/artifacts.py` | 理论侧工件 |
| `langchain/*` | LangChain 封装（与 graph 路径相关） |
| `skills/bridge.py` | Skills 桥接（若启用） |
| `app/client/cli.py` | 命令行客户端（可选） |

端点权威清单：[`API-COVERAGE.md`](API-COVERAGE.md)。

---

## 10. 测试怎么跟读

| 类型 | 路径 | 用途 |
|------|------|------|
| API 冒烟 / 分域 | `tests/api/` | 对路由做黑盒 |
| 单元 | `tests/unit/`、`tests/test_*.py` | 收尾、公式规范化等 |
| 探针 | `scripts/api_quant_probe.py` | 量化延迟 |

读完某域后，打开对应 `tests/api/test_*.py` 看「期望行为」。

---

## 推荐日历（约 8–10 个半日）

| 半日 | 主题 |
|------|------|
| 1 | §0 文档 + §1 入口配置 |
| 2–3 | §2 对话主路径（可画时序图） |
| 4 | §3 MCP |
| 5 | §4 LangGraph / 场景工作流 |
| 6 | §5 课题与理论工作区 |
| 7 | §6 记忆与 RAG |
| 8 | §7–§8 验证实验导出 |

前端以后再开：`doc/web.md` → `app/web/src/components/ChatPage.tsx` → hooks。

---

## 读源码小技巧

1. **先搜调用方**：`grep` / IDE「Find references」，比从上往下扫更快。  
2. **SSE 事件名**在 `shared/schemas.py` 的 `StreamChunk.type` 与 `api/chat.py` 对齐。  
3. **两套 Agent 路径**：`legacy`（`base.py`）与 `langgraph`（`subagent` + `graph/*`），由配置与编排器选择。  
4. **课题删除**：`DELETE /v1/projects/{id}?purge=true` → `api/projects.py` → sessions + RAG + 磁盘工作区。  
5. 模块顶部的「职责 / 架构位置 / Debug」块就是为阅读准备的导航——优先读这些块。

---

## 修订记录

- 2026-07-20：初版（后端阅读顺序；前端刻意省略）。
- 2026-07-22：对齐 v2.2 理论侧——去掉已删除的 Campaign / Supervisor 路径，补场景工作流与 Artifact。

---
name: Task 03 — 工具持久化、截断、白名单
task_id: p3-tool-persist
status: completed
---

# Task 03：SQLite tool_calls 持久化 + 截断 + 白名单

## 目标

在 assistant 消息上持久化 MCP 工具调用记录，工具结果写入 LLM 上下文前截断，并增加可选工具白名单过滤。

## 前置条件

- [x] Task 1 完成（LangChain 适配层）
- [x] Task 2 完成（MultiServerMCPClient、限定名）
- [x] 仅在 `dev` 分支工作，不 push 远程

## 步骤

### Step 1 — Schema（`shared/schemas.py`）

1. 增加 `PersistedToolCall` 模型（id、name、arguments、result、status）
2. 在 `ChatMessage` 上增加可选 `tool_calls` 字段

### Step 2 — SQLite 迁移（`server/memory/sqlite_store.py`）

1. 经 `_migrate()` 增加 `tool_calls TEXT` 列
2. 读写时 JSON 序列化/反序列化

### Step 3 — 配置（`server/config.py`、`.env.example`）

1. `MCP_TOOL_RESULT_MAX_CHARS`（默认 8000）
2. `MCP_TOOL_WHITELIST` — 逗号分隔 glob 模式（空 = 全部）
3. `MCP_TOOL_WHITELIST_PATH` — 可选 JSON，含 `global` + 按 Agent 模式

### Step 4 — 白名单 + 截断模块

1. `server/mcp/whitelist.py` — 模式匹配、加载 JSON、过滤工具列表
2. `server/mcp/truncation.py` — `truncate_tool_result()`，附摘要提示

### Step 5 — MCPClient + GeneralAgent

1. `get_openai_tools(agent_name=...)` 应用白名单
2. `_run_tool_loop` 对 `api_messages` 截断结果，收集 `PersistedToolCall` 记录
3. `run()` 在使用 tool loop 时将 `tool_calls` 持久化到 assistant 消息

### Step 6 — 测试

1. Session store tool_calls 往返（memory + sqlite）
2. 截断单元测试
3. 白名单过滤单元测试
4. Agent 在 fake tool loop 后持久化 tool_calls

### Step 7 — Benchmark 与提交

1. `pytest tests/ -q`
2. 通过后 → `benchmarks/task-03-tool-persist.md`
3. 在 `dev` 上逻辑提交
4. 主计划标记 `p3-tool-persist` completed

## 不在范围内（Task 4）

- LangGraph ReAct 子图
- 经 LangGraph 的 SSE 事件映射

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 计划文件 | done | 本文件 |
| Schema + SQLite | done | PersistedToolCall、tool_calls 列 |
| 配置 + 模块 | done | truncation、whitelist |
| Agent 集成 | done | GeneralAgent 持久化 + 截断 |
| 测试 | done | 53 passed |
| Benchmark 文档 | done | benchmarks/task-03-tool-persist.md |

---
name: Task 04 — LangGraph ReAct 子图
task_id: p3-langgraph-react
status: completed
---

# Task 04：LangGraph ReAct 子图 + SSE 映射 + 功能开关

## 目标

当 `ORCHESTRATION_BACKEND=langgraph` 且启用工具时，用 LangGraph ReAct 子图替代 `GeneralAgent._run_tool_loop`。将图事件映射为现有 `StreamChunk` SSE 类型。保留 Task 3 的 tool_calls 持久化与截断。

## 前置条件

- [x] Task 1：`get_chat_model()` 于 `server/langchain/llm.py`
- [x] Task 2：MCP `MultiServerMCPClient`、限定工具名
- [x] Task 3：tool_calls SQLite 持久化、截断、白名单
- [x] 仅在 `dev` 分支工作，不 push 远程

## 步骤

### Step 1 — LangChain MCP 工具（`server/langchain/tools.py`）

1. 经 `call_tool(qualified_name, args)` 从 `MCPClient` registry 构建 `StructuredTool` 列表
2. 经现有 `get_openai_tools(agent_name=...)` 应用白名单

### Step 2 — ReAct 子图（`server/graph/`）

1. `state.py` — `ReactState`：messages、tool_call_records、tool_rounds
2. `nodes.py` — `call_model`（绑定 tools，thinking 关）、`execute_tools`（截断 + 持久化）、`call_model_final`（thinking 开，无 tools）
3. `react.py` — 编译 `StateGraph`，条件边 + 最大轮次
4. `streaming.py` — `astream_events` → `StreamChunk` 映射

### Step 3 — GeneralAgent 集成

1. 当 `orchestration_backend == "langgraph"` 且启用 tools → `_run_langgraph_tool_loop`
2. 否则 → 现有 `_run_tool_loop`
3. `run()` 中复用会话持久化逻辑

### Step 4 — 测试

1. `tests/test_langgraph_react.py` — mock ChatModel + StructuredTool，图 SSE 映射
2. 现有 legacy 测试不变（`ORCHESTRATION_BACKEND=legacy`）

### Step 5 — 验证与文档

1. `ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true pytest tests/ -q`
2. `ORCHESTRATION_BACKEND=legacy pytest tests/ -q`
3. CLI 冒烟
4. `benchmarks/task-04-langgraph-react.md`
5. 在 `dev` 上逻辑提交
6. 主计划标记 `p3-langgraph-react` completed

## 不在范围内（Task 5）

- 多 Agent supervisor 图
- theory/experiment/literature 子 Agent

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 计划文件 | done | 本文件 |
| 图 + 工具 | done | server/graph/、server/langchain/tools.py |
| Agent 集成 | done | GeneralAgent 中 ORCHESTRATION_BACKEND 开关 |
| 测试 | done | 56 passed（langgraph + legacy） |
| Benchmark | done | benchmarks/task-04-langgraph-react.md |

---
name: Task 05 — 多 Agent supervisor 路由
task_id: p4-multi-agent
status: completed
---

# Task 05：Supervisor 路由 + theory/experiment/literature 子图

## 目标

Supervisor 路由图：classify_intent → 路由至子图；API/CLI 扩展；SSE agent_name/handoff/a2a_task_id。

## 前置条件

- [x] Task 4：`server/graph/` 中 LangGraph ReAct 子图
- [x] `ORCHESTRATION_BACKEND=langgraph` 路径可用
- [x] `get_openai_tools()` 上按 `agent_name` 的 MCP 白名单
- [x] 仅在 `dev` 分支工作，不 push 远程

## 步骤

### Step 1 — Agent 配置 + prompts

1. 扩展 `server/llm/prompts.py`，增加 theory/experiment/literature prompts
2. `server/agents/config.py` — Agent 注册表（name、prompt、默认白名单模式）
3. `mcp_tool_whitelist.json` — 按 Agent 的工具 glob

### Step 2 — 意图路由

1. `server/graph/router.py` — `classify_intent(message, mode)` 规则 + `mode=math` → theory

### Step 3 — SubAgent 运行器 + 编排器

1. `server/agents/subagent.py` — 参数化 ReAct 运行器（name + prompt + whitelist）
2. `server/agents/orchestrator.py` — 路由、agent_handoff SSE、委托 SubAgent
3. 仅 LangGraph backend；legacy 仍用 `GeneralAgent`

### Step 4 — Schema + API + CLI

1. `ChatRequest`：可选 `agent`、`auto_route`（省略 agent 时默认 true）
2. `StreamChunk`：`agent_handoff` 类型、`route_reason`、`from_agent`、`to_agent`
3. `chat.py` — langgraph 时用 orchestrator；meta 含 route_reason
4. CLI：`--agent theory`、`--auto-route`

### Step 5 — 测试 + benchmark

1. `tests/test_multi_agent.py` — 3 条路由 prompt + handoff SSE + legacy 不变
2. `pytest tests/ -q` + CLI 冒烟
3. `benchmarks/task-05-multi-agent.md`
4. 在 `dev` 上逻辑提交
5. 主计划标记 `p4-multi-agent` completed

## 不在范围内（Task 6）

- RAG / 向量记忆
- Web UI Agent 时间线

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 计划文件 | done | 本文件 |
| Agent 配置 | done | config.py、prompts、mcp_tool_whitelist.json |
| 路由 + 编排 | done | router.py、subagent.py、orchestrator.py |
| API/CLI/SSE | done | chat.py、cli.py、schemas.py |
| 测试 + benchmark | done | 65 passed，benchmarks/task-05-multi-agent.md |

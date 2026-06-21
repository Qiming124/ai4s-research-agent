---
name: Task 02 — MCP langchain-mcp-adapters
task_id: p3-mcp-adapters
status: completed
---

# Task 02：MCP 迁移至 MultiServerMCPClient

## 目标

将 MCP 连接逻辑迁移至 `langchain-mcp-adapters` 的 `MultiServerMCPClient`，同时保留：
- `mcp_servers.json` 配置格式
- `{server}__{tool}` 限定工具名（ToolRegistry）
- 稳定的 `get_mcp_client()` / `MCPClient` API，供 GeneralAgent 使用
- `GET /v1/mcp/status` 行为
- `server/main.py` 中应用 lifespan 的 connect/disconnect

## 前置条件

- [x] Task 1 已在 `dev` 完成（LangChain 依赖、`server/langchain/llm.py`）
- [x] 仅在 `dev` 分支工作，不 push 远程

## 步骤

### Step 1 — 配置桥接（`server/langchain/mcp.py`）

1. `build_multiserver_connections(configs)` → `dict[str, StdioConnection]`
2. 将 `command: "python"` 映射为 `sys.executable`
3. 透传 `args`、`env`，设置 `transport: "stdio"`
4. 跳过 disabled server

### Step 2 — 重构 `server/mcp/client.py`

1. 从桥接连接创建 `MultiServerMCPClient`
2. `connect()` 时：将 `client.session(server_name)` 进入 `AsyncExitStack`（持久会话）
3. 经 `session.list_tools()` 注册工具到现有 `ToolRegistry`，名称为 `server__tool`
4. `call_tool()` 不变：经 registry 解析，调用 `session.call_tool`
5. `close()`  teardown exit stack 并清空 registry
6. 保留 `get_mcp_client`、`reset_mcp_client`、`build_mcp_status` 签名

### Step 3 — Lifespan 集成

- `server/main.py` 已调用 `get_mcp_client()` / `_mcp_client.close()` — 确认无需变更

### Step 4 — 测试

```bash
pytest tests/test_mcp.py tests/test_api.py -q
pytest tests/ -q
```

### Step 5 — Benchmark 与提交

1. 通过后 → `benchmarks/task-02-mcp-adapters.md`
2. 逻辑提交：bridge 模块、client 重构、benchmark
3. 主计划 frontmatter 标记 `p3-mcp-adapters` completed

## 不在范围内（Task 3–4）

- SQLite `tool_calls` 持久化
- LangGraph ReAct tool loop
- 工具结果截断 / Agent 白名单（后续 Phase 3 项）

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 计划文件 | done | 本文件 |
| 配置桥接 | done | server/mcp/config.py + langchain/mcp 再导出 |
| Client 重构 | done | MultiServerMCPClient.session() 持久连接 |
| 测试 | done | 44 passed |
| Benchmark 文档 | done | benchmarks/task-02-mcp-adapters.md |

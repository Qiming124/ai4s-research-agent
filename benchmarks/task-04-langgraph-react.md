# Task 04 — LangGraph ReAct 子图

验证当 `ORCHESTRATION_BACKEND=langgraph` 时，LangGraph ReAct 工具循环替代 `_run_tool_loop`，保留 SSE 映射与 Task 3 持久化能力。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

确保 `.env` 中包含有效的 `DEEPSEEK_API_KEY`。

## 自动化测试

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true pytest tests/ -q
ORCHESTRATION_BACKEND=legacy pytest tests/ -q
```

预期：两种 backend 各 **56 passed**。

LangGraph 专项覆盖：

```bash
pytest tests/test_langgraph_react.py -q
```

## 功能开关

```bash
grep ORCHESTRATION_BACKEND .env.example
# ORCHESTRATION_BACKEND=legacy
```

设置 `ORCHESTRATION_BACKEND=langgraph` 可将 `GeneralAgent` 工具循环路由至 LangGraph 路径。默认仍为 `legacy`。

## 架构（Task 4）

| 路径 | 模块 |
|------|------|
| ReAct 状态 | `server/graph/state.py` |
| 节点（`call_model`、`execute_tools`） | `server/graph/nodes.py` |
| 图编译 | `server/graph/react.py` |
| SSE 映射 | `server/graph/streaming.py` |
| MCP → StructuredTool | `server/langchain/tools.py` |
| Agent 集成 | `server/agents/base.py`（`_run_langgraph_tool_loop`） |

## 手动验证（可选，需 API Key + MCP）

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true uvicorn server.main:app --port 8000
# 另一终端:
research-agent-cli chat "List files in data/mcp_files" --stream
```

预期 SSE 事件：`tool_call_start`、`tool_call_result`、`content`、`done`。

## 尚未纳入范围（Task 5）

- 多 Agent supervisor 路由（`p4-multi-agent`）
- theory / experiment / literature 子图
- `agent_handoff` SSE 事件

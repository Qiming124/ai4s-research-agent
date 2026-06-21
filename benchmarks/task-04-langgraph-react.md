# Task 04 — LangGraph ReAct Subgraph

Verify LangGraph ReAct tool loop replaces `_run_tool_loop` when `ORCHESTRATION_BACKEND=langgraph`, with SSE mapping and Task 3 persistence preserved.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

Ensure `.env` contains a valid `DEEPSEEK_API_KEY`.

## Automated tests

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true pytest tests/ -q
ORCHESTRATION_BACKEND=legacy pytest tests/ -q
```

Expected: **56 passed** for each backend.

LangGraph-specific coverage:

```bash
pytest tests/test_langgraph_react.py -q
```

## Feature flag

```bash
grep ORCHESTRATION_BACKEND .env.example
# ORCHESTRATION_BACKEND=legacy
```

Set `ORCHESTRATION_BACKEND=langgraph` to route `GeneralAgent` tool loops through the LangGraph path. Default remains `legacy`.

## Architecture (Task 4)

| Path | Module |
|------|--------|
| ReAct state | `server/graph/state.py` |
| Nodes (`call_model`, `execute_tools`) | `server/graph/nodes.py` |
| Graph compiler | `server/graph/react.py` |
| SSE mapping | `server/graph/streaming.py` |
| MCP → StructuredTool | `server/langchain/tools.py` |
| Agent integration | `server/agents/base.py` (`_run_langgraph_tool_loop`) |

## Manual verification (optional, requires API key + MCP)

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true uvicorn server.main:app --port 8000
# In another terminal:
research-agent-cli chat "List files in data/mcp_files" --stream
```

Expect SSE events: `tool_call_start`, `tool_call_result`, `content`, `done`.

## What is not in scope yet (Task 5)

- Multi-agent supervisor routing (`p4-multi-agent`)
- theory / experiment / literature sub-graphs
- `agent_handoff` SSE events

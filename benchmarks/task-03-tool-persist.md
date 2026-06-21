# Task 03 — Tool Calls Persistence, Truncation, Whitelist

Verify assistant messages persist MCP `tool_calls` in SQLite, tool results truncate before LLM context, and optional whitelist filters tools.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

## Automated tests

```bash
pytest tests/test_tool_persist.py tests/test_session.py -q
pytest tests/ -q
```

Expected: all tests pass (53+). Key cases:
- `test_session_store_tool_calls` — memory + sqlite round-trip
- `test_truncate_tool_result_over_limit` — truncation with summary hint
- `test_general_agent_persists_tool_calls` — agent writes tool records on completion

## Manual verification — GET session API

With MCP enabled, after a tool-using chat:

```bash
export ENABLE_MCP=true
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Send a chat that triggers a tool, then fetch session:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"List files in mcp_files","enable_tools":true}' | python -m json.tool

# Use session_id from response:
curl -s http://127.0.0.1:8000/v1/sessions/<session_id> | python -m json.tool
```

Expected: assistant message includes `tool_calls` array with `id`, `name`, `arguments`, `result`, `status`.

## Config

```bash
grep MCP_TOOL .env.example
```

- `MCP_TOOL_RESULT_MAX_CHARS=8000` — truncate tool results for LLM context
- `MCP_TOOL_WHITELIST` — comma-separated glob patterns (empty = all)
- `MCP_TOOL_WHITELIST_PATH` — optional JSON with `global` + `agents` mapping

## What is not in scope yet

- LangGraph ReAct tool loop (Task 4)
- Web UI tool timeline from persisted `tool_calls` (Task 7)

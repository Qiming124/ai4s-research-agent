# Task 02 — MCP MultiServerMCPClient Migration

Verify MCP connects via `langchain-mcp-adapters` while preserving `mcp_servers.json`, `server__tool` names, and existing APIs.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

Note: `langchain-mcp-adapters` is pinned to `<0.2` for compatibility with `langchain-core` 0.3.x.

## Automated tests

```bash
pytest tests/test_mcp.py tests/test_api.py -q
pytest tests/ -q
```

Expected: all tests pass (43+). MCP integration test connects 3 builtin servers and exercises filesystem read/write.

## Manual verification — MCP status API

Start server with MCP enabled:

```bash
export DEEPSEEK_API_KEY=sk-your-key
export ENABLE_MCP=true
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/v1/mcp/status | python -m json.tool
```

Expected:
- `server_enabled`: true
- `connected`: true
- Three servers: `web_search`, `arxiv`, `filesystem` with `connected: true`
- Tools use qualified names like `arxiv__search_papers`, `filesystem__read_file`

## Manual verification — Python REPL

```bash
python - <<'PY'
import asyncio
from server.config import get_settings
from server.mcp.client import MCPClient, reset_mcp_client

async def main():
    get_settings.cache_clear()
    reset_mcp_client()
    settings = get_settings().model_copy(update={"enable_mcp": True})
    client = MCPClient(settings)
    await client.connect()
    names = {t["function"]["name"] for t in client.get_openai_tools()}
    print("tools:", sorted(names)[:3], "...")
    assert any(n.startswith("arxiv__") for n in names)
    await client.close()
    reset_mcp_client()
    print("mcp-adapters-ok")

asyncio.run(main())
PY
```

Expected output includes `mcp-adapters-ok`.

## Architecture notes

- `server/langchain/mcp.py` bridges `mcp_servers.json` → `MultiServerMCPClient` stdio connections
- `server/mcp/client.py` opens persistent sessions via `MultiServerMCPClient.session()` in app lifespan
- `ToolRegistry` still emits `{server}__{tool}` for OpenAI function calling
- `GeneralAgent` unchanged — still uses `get_mcp_client()` / `call_tool()`

## Out of scope (Task 3–4)

- SQLite `tool_calls` persistence
- LangGraph ReAct tool loop

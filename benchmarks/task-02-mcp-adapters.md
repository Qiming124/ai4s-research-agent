# Task 02 — MCP MultiServerMCPClient 迁移

验证 MCP 通过 `langchain-mcp-adapters` 连接，同时保留 `mcp_servers.json`、`server__tool` 命名与现有 API。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

说明：`langchain-mcp-adapters` 固定为 `<0.2`，以兼容 `langchain-core` 0.3.x。

## 自动化测试

```bash
pytest tests/test_mcp.py tests/test_api.py -q
pytest tests/ -q
```

预期：全部测试通过（43+）。MCP 集成测试连接 3 个内置 server 并演练 filesystem 读写。

## 手动验证 — MCP 状态 API

启用 MCP 后启动服务：

```bash
export DEEPSEEK_API_KEY=sk-your-key
export ENABLE_MCP=true
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

在另一终端：

```bash
curl -s http://127.0.0.1:8000/v1/mcp/status | python -m json.tool
```

预期：
- `server_enabled`: true
- `connected`: true
- 三个 server：`web_search`、`arxiv`、`filesystem`，均为 `connected: true`
- 工具使用限定名，如 `arxiv__search_papers`、`filesystem__read_file`

## 手动验证 — Python REPL

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

预期输出包含 `mcp-adapters-ok`。

## 架构说明

- `server/langchain/mcp.py` 将 `mcp_servers.json` 桥接为 `MultiServerMCPClient` stdio 连接
- `server/mcp/client.py` 在应用 lifespan 中通过 `MultiServerMCPClient.session()` 建立持久会话
- `ToolRegistry` 仍为 OpenAI function calling 输出 `{server}__{tool}`
- `GeneralAgent` 未变 — 仍使用 `get_mcp_client()` / `call_tool()`

## 不在范围内（Task 3–4）

- SQLite `tool_calls` 持久化
- LangGraph ReAct 工具循环

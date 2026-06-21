# Task 01 — LangChain Dependencies & Adapter Layer

Verify that LangChain stack is installed and `get_chat_model()` produces DeepSeek-compatible responses aligned with `DeepSeekClient` settings.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

Ensure `.env` contains a valid `DEEPSEEK_API_KEY`.

## Automated tests

```bash
pytest tests/test_langchain_llm.py -q
pytest tests/ -q
```

Expected: all tests pass (including parity check vs `DeepSeekClient._build_create_kwargs`).

## Manual verification (Python REPL)

```bash
python - <<'PY'
import asyncio
from server.config import get_settings
from server.langchain.llm import build_chat_model_kwargs, get_chat_model

settings = get_settings()
print("ORCHESTRATION_BACKEND:", settings.orchestration_backend)  # legacy
print("kwargs:", build_chat_model_kwargs(settings))

async def main():
    model = get_chat_model()
    resp = await model.ainvoke("Reply with exactly: langchain-ok")
    print("content:", resp.content.strip())

asyncio.run(main())
PY
```

Expected output includes `ORCHESTRATION_BACKEND: legacy` and `content: langchain-ok`.

## Config flag

`ORCHESTRATION_BACKEND` defaults to `legacy`. Production chat path still uses `server/llm/client.py`. LangGraph migration is Task 2–4.

```bash
grep ORCHESTRATION_BACKEND .env.example
# ORCHESTRATION_BACKEND=legacy
```

## What is not in scope yet

- MCP via `langchain-mcp-adapters` (Task 2)
- LangGraph ReAct tool loop (Task 4)
- Removing `DeepSeekClient`

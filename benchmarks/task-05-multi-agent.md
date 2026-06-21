# Task 05 — Multi-Agent Supervisor Routing

Verify supervisor routing to theory/experiment/literature sub-agents, API/CLI extensions, and SSE handoff events when `ORCHESTRATION_BACKEND=langgraph`.

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
pytest tests/test_multi_agent.py -q
```

Expected: **65 passed** (langgraph + legacy).

## Feature flag

Multi-agent routing is active only when:

```bash
ORCHESTRATION_BACKEND=langgraph
```

With `ORCHESTRATION_BACKEND=legacy`, the API/CLI still accept `agent` / `auto_route` fields but routing uses `GeneralAgent` only (no supervisor handoff).

## Architecture (Task 5)

| Component | Path |
|-----------|------|
| Agent registry + prompts | `server/agents/config.py`, `server/llm/prompts.py` |
| Intent router | `server/graph/router.py` |
| SubAgent ReAct runner | `server/agents/subagent.py` |
| Supervisor orchestrator | `server/agents/orchestrator.py` |
| Per-agent tool whitelist | `mcp_tool_whitelist.json`, `server/mcp/whitelist.py` |
| API routing | `server/api/chat.py` |
| CLI flags | `client/cli.py` (`--agent`, `--auto-route`) |
| SSE schema | `shared/schemas.py` (`agent_handoff`, `route_reason`, `a2a_task_id`) |

## Agent tool subsets

| Agent | Tools |
|-------|-------|
| `general` | all (`*`) |
| `theory` | none (`__none__`) |
| `experiment` | `filesystem__*` |
| `literature` | `arxiv__*`, `web_search__*` |

## API examples

```bash
# Auto-route (default)
curl -s -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"检索 arxiv 上 Adam 优化器论文"}'

# Explicit agent
curl -s -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"分析实验","agent":"experiment","auto_route":false}'

# mode=math → theory agent
curl -s -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"推导损失","mode":"math"}'
```

SSE events include `meta` (with `route_reason`), `agent_handoff`, and chunks with `agent_name` / `a2a_task_id`.

## CLI examples

```bash
research-agent-cli --agent theory --no-auto-route
research-agent-cli --auto-route
research-agent-cli --mode math
```

## Manual verification (optional, requires API key + MCP)

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true uvicorn server.main:app --port 8000
research-agent-cli --auto-route
```

Expect handoff line for literature/experiment prompts and `agent_name` on stream chunks.

## What is not in scope yet (Task 6)

- RAG / L3 vector memory
- Web agent timeline UI

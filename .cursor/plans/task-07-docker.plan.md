---
name: Task 07 — Docker + observability
task_id: p6-docker
status: completed
---

# Task 07: Dockerfile + docker-compose + structured logging + token usage stats

## Goal

Containerize the full stack (web build + Python app), add structured request/tool logging, and persist token usage aggregates in SQLite.

## Preconditions

- [x] Tasks 1–6 on `dev`: LangChain, MCP, multi-agent, RAG with Chroma at `./data/chroma`
- [x] Work on `dev` only, no remote push

## Steps

### Step 1 — Structured logging

1. `server/observability/context.py` — ContextVars: `request_id`, `session_id`, `agent_name`
2. `server/observability/structured.py` — JSON log formatter + `log_event()` helper
3. `server/observability/middleware.py` — FastAPI middleware: assign `X-Request-ID`, log HTTP latency
4. `server/config.py` — `LOG_FORMAT=text|json` (default `text`; Docker uses `json`)
5. Integrate: `setup_logging`, `main.py` middleware, `mcp/client.call_tool` tool latency logs

### Step 2 — Token usage aggregation

1. `server/observability/token_usage.py` — SQLite table `token_usage_events` in sessions.db
2. `record_token_usage(session_id, agent_name, usage)` from agent done handlers
3. `server/api/stats.py` — `GET /v1/stats/tokens` (filter by session/agent/day)
4. Schemas in `shared/schemas.py`

### Step 3 — Docker delivery

1. `docker/Dockerfile` — multi-stage: Node 20 build web + Python 3.12 slim runtime
2. `docker/docker-compose.yml` — app service, `env_file: ../.env`, volume `../data:/app/data`
3. `docker/.env.example` — Docker-oriented defaults (paths, LOG_FORMAT=json)
4. `docker/README.md` — build/run/healthcheck instructions
5. `.dockerignore` — exclude `.venv`, `node_modules`, git, caches

### Step 4 — Tests + benchmark + plan update

1. `tests/test_observability.py` — context, token store, stats API, middleware header
2. `pytest tests/ -q` + curl smoke
3. `benchmarks/task-07-docker.md`
4. Logical commits on `dev`
5. Mark `p6-docker` completed in main plan

## Out of scope (Task 8)

- Web three-column layout, tool timeline UI, RAG management UI, Playwright E2E

## Status log

| Step | Status | Notes |
|------|--------|-------|
| Plan file | done | this file |
| Structured logging | done | JSON formatter, middleware, MCP tool latency |
| Token stats | done | SQLite table + `/v1/stats/tokens` |
| Docker | done | Dockerfile, compose, README; build skip (no daemon) |
| MCP subprocess fix | done | lazy `server/mcp/__init__.py` imports |
| Tests + benchmark | done | 84 passed, benchmarks/task-07-docker.md |

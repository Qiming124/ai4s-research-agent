# Task 07 — Docker + Observability

Verify container delivery, structured logging, and token usage aggregation.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

Ensure `.env` contains a valid `DEEPSEEK_API_KEY` for live smoke (optional).

## Automated tests

```bash
pytest tests/ -q
pytest tests/test_observability.py -q
```

Expected: **84 passed** (includes 6 observability tests).

## New components (Task 7)

| Component | Path |
|-----------|------|
| Structured logging | `server/observability/structured.py`, `middleware.py`, `context.py` |
| Token usage store | `server/observability/token_usage.py` (SQLite `token_usage_events`) |
| Stats API | `GET /v1/stats/tokens` — `server/api/stats.py` |
| Config | `LOG_FORMAT`, `ENABLE_TOKEN_STATS` in `server/config.py`, `.env.example` |
| Docker | `docker/Dockerfile`, `docker/docker-compose.yml`, `docker/README.md` |
| MCP subprocess fix | lazy imports in `server/mcp/__init__.py` |

## Structured logging fields

When `LOG_FORMAT=json`, each log line is JSON with:

- `request_id` — from `X-Request-ID` header or auto-generated (middleware)
- `session_id`, `agent_name` — set during chat turns
- `tool_name`, `latency_ms` — MCP tool calls (`tool_call_complete` / `tool_call_error`)
- HTTP events: `http_request_start`, `http_request_complete`

## Token stats API

```bash
curl -s http://127.0.0.1:8000/v1/stats/tokens
curl -s 'http://127.0.0.1:8000/v1/stats/tokens?session_id=<uuid>&agent_name=general'
curl -s 'http://127.0.0.1:8000/v1/stats/tokens?day=2026-06-21'
```

Disable persistence: `ENABLE_TOKEN_STATS=false`.

## Docker quick start

```bash
cp .env.example .env   # set DEEPSEEK_API_KEY
mkdir -p data/mcp_files data/chroma

docker compose -f docker/docker-compose.yml up --build
```

- UI + API: http://localhost:8000
- Health: `curl -s http://localhost:8000/health`
- Volumes: `data/` → sessions.db, mcp_files, chroma

Build only:

```bash
docker compose -f docker/docker-compose.yml build
```

## Docker build smoke (Task 7 run)

| Check | Result |
|-------|--------|
| `pytest tests/ -q` | **PASS** — 84 passed |
| `docker compose ... build` | **SKIP** — Docker daemon not available in CI/sandbox (`/var/run/docker.sock` missing) |

Re-run build locally when Docker is installed.

## What is not in scope (Task 8)

- Web three-column layout, tool timeline UI, RAG management UI, Playwright E2E

## Blockers / notes for Task 8 (p7-web)

- Token stats API (`/v1/stats/tokens`) is ready for top-bar token usage widget
- Structured logs include `agent_name`, `tool_name`, `latency_ms` — align SSE tool timeline with same field names
- Docker image serves built `web/dist`; Task 8 UI changes require `docker compose up --build` to refresh
- `X-Request-ID` header available for client-side debug correlation
- RAG document API exists (`/v1/documents`) but no Web management UI yet — Task 8 deliverable

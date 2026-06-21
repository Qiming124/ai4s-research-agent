# Docker deployment — AI4S Research Agent

Single-container deployment: FastAPI + built React UI + embedded Chroma + MCP stdio servers.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A valid `DEEPSEEK_API_KEY` in the repo root `.env`

## Quick start

From the **repository root**:

```bash
cp .env.example .env
# Edit .env and set DEEPSEEK_API_KEY

mkdir -p data/mcp_files data/chroma

docker compose -f docker/docker-compose.yml up --build
```

Open http://localhost:8000 — the server serves `web/dist` and API routes.

## Configuration

| Mechanism | Purpose |
|-----------|---------|
| `env_file: ../.env` | Loads secrets and overrides from repo root |
| `environment:` in compose | Container paths for data volumes |
| `../data:/app/data` | Persists `sessions.db`, MCP files, Chroma index |

Recommended container paths (set automatically in compose):

- `SESSION_DB_PATH=/app/data/sessions.db`
- `MCP_ALLOWED_DIRS=/app/data/mcp_files`
- `RAG_CHROMA_PATH=/app/data/chroma`
- `LOG_FORMAT=json` — structured logs with `request_id`, `session_id`, `agent_name`, `tool_name`, `latency_ms`

See `docker/.env.example` for a Docker-focused template.

## Health check

```bash
curl -s http://localhost:8000/health
```

Compose and the Dockerfile both probe `/health` every 30s.

## Token usage stats

After chat turns complete, token usage is stored in SQLite (`token_usage_events` table in `sessions.db`):

```bash
curl -s 'http://localhost:8000/v1/stats/tokens'
curl -s 'http://localhost:8000/v1/stats/tokens?agent_name=literature&day=2026-06-21'
```

Disable with `ENABLE_TOKEN_STATS=false`.

## MCP in Docker

MCP servers run as Python subprocesses inside the same container (`mcp_servers.json`). Place experiment logs under `data/mcp_files/` on the host; they appear at `/app/data/mcp_files` in the container.

No separate Chroma service is required — the app uses Chroma `PersistentClient` under `data/chroma`.

## Build only

```bash
docker compose -f docker/docker-compose.yml build
```

## Stop

```bash
docker compose -f docker/docker-compose.yml down
```

Data in `data/` is retained on the host volume.

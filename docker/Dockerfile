# ── Stage 1: build web frontend ──────────────────────────────
FROM node:20-alpine AS web-build

WORKDIR /web
COPY app/web/package.json app/web/package-lock.json ./
RUN npm ci --ignore-scripts || npm install
COPY app/web/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /repo

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app/server/ ./app/server/
COPY app/client/ ./app/client/
COPY app/shared/ ./app/shared/
COPY conf/mcp_servers.json ./conf/mcp_servers.json

RUN pip install ".[rag]"

COPY --from=web-build /web/dist ./app/web/dist

RUN mkdir -p /repo/data/mcp_files /repo/data/chroma /repo/log

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "app"]

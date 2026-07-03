# ── Stage 1: build web frontend ──────────────────────────────
FROM node:20-alpine AS web-build

WORKDIR /web
COPY app/web/package.json app/web/package-lock.json ./
RUN npm ci --ignore-scripts || npm install
COPY app/web/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────
FROM python:3.12-slim AS runtime

# 设为 1 时安装 sentence-transformers（会拉取 torch，镜像更大、构建更慢）
ARG INSTALL_RAG_EXTRA=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /repo

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && if [ "$INSTALL_RAG_EXTRA" = "1" ]; then \
         apt-get install -y --no-install-recommends build-essential; \
       fi \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app/server/ ./app/server/
COPY app/client/ ./app/client/
COPY app/shared/ ./app/shared/
# 复制 conf（.env 由 .dockerignore 排除）；运行时 compose 会挂载宿主机 conf 覆盖
COPY conf/ ./conf/

RUN if [ "$INSTALL_RAG_EXTRA" = "1" ]; then \
      pip install ".[rag,pdf]"; \
    else \
      pip install ".[pdf]"; \
    fi

# 预下载 chroma_default 嵌入模型，避免容器首次启动长时间阻塞健康检查
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"

COPY --from=web-build /web/dist ./app/web/dist

RUN mkdir -p /repo/data/mcp_files /repo/data/chroma /repo/data/theory /repo/data/experiments/logs /repo/data/experiments/notebooks /repo/log
COPY data/theory/ ./data/theory/
COPY data/experiments/configs/ ./data/experiments/configs/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "app"]

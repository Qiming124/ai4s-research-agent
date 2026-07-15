# ── Stage 1: build web frontend ──────────────────────────────
FROM node:20-alpine AS web-build

WORKDIR /web
COPY app/web/package.json app/web/package-lock.json ./
RUN npm ci --ignore-scripts || npm install
COPY app/web/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────
FROM python:3.12-slim AS runtime

# 可选 apt 大包（默认全关：Debian 官方源在国内常 <20KB/s，texlive/pandoc 会卡数小时）
ARG INSTALL_RAG_EXTRA=0
ARG INSTALL_PANDOC=0
ARG INSTALL_TEXLIVE=0
# apt 镜像（默认阿里云；海外可构建时传 APT_MIRROR=deb.debian.org）
ARG APT_MIRROR=mirrors.aliyun.com

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /repo

# 仅 curl（HEALTHCHECK）。MD/DOCX/PDF 走 pip：markdown_renderer / python-docx / reportlab
# 中文字体已打包在 app/server/export/fonts/
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl; \
    if [ "$INSTALL_RAG_EXTRA" = "1" ]; then \
      apt-get install -y --no-install-recommends build-essential; \
    fi; \
    if [ "$INSTALL_PANDOC" = "1" ]; then \
      apt-get install -y --no-install-recommends pandoc; \
    else \
      echo "INSTALL_PANDOC=0 — MD→HTML uses in-repo renderer"; \
    fi; \
    if [ "$INSTALL_TEXLIVE" = "1" ]; then \
      apt-get install -y --no-install-recommends texlive-xetex fonts-noto-cjk \
        || echo "WARN: texlive failed; PDF uses reportlab fallback"; \
    else \
      echo "INSTALL_TEXLIVE=0 — PDF uses reportlab/HTML"; \
    fi; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app/server/ ./app/server/
COPY app/client/ ./app/client/
COPY app/shared/ ./app/shared/
# 复制 conf（.env 由 .dockerignore 排除）；运行时 compose 会挂载宿主机 conf 覆盖
COPY conf/ ./conf/

RUN if [ "$INSTALL_RAG_EXTRA" = "1" ]; then \
      pip install ".[rag,pdf,docx,export]"; \
    else \
      pip install ".[pdf,docx,export]"; \
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

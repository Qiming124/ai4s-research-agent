# Docker 部署 — AI4S Research Agent

单容器部署：FastAPI + 构建后的 React UI + 内嵌 Chroma + MCP stdio 服务。

## 前置条件

- Docker Engine 24+ 与 Docker Compose v2
- 在 `conf/.env` 中配置有效的 `DEEPSEEK_API_KEY`
- 能拉取基础镜像（`node:20-alpine`、`python:3.12-slim`）。国内网络若出现 `auth.docker.io` / `i/o timeout`，见下方「镜像加速」

## 镜像加速（国内 / Docker Hub 超时）

构建报错示例：

```text
failed to fetch oauth token: Post "https://auth.docker.io/token": dial tcp ... i/o timeout
```

**Docker Desktop（Windows + WSL）**：Settings → Docker Engine，在 JSON 中加入 `registry-mirrors`（任选可用源，示例）：

```json
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://dockerpull.com"
  ]
}
```

Apply & Restart 后执行 `docker info` 确认 mirrors 已生效，再重新 `build`。

**Linux**：编辑 `/etc/docker/daemon.json` 同样配置后 `sudo systemctl restart docker`。

本仓库 Dockerfile **未使用** `# syntax=docker/dockerfile:1`，避免额外拉取 `docker/dockerfile` 前端镜像。

## 快速启动

在**仓库根目录**执行：

```bash
cp conf/.env.example conf/.env
# 编辑 conf/.env 并设置 DEEPSEEK_API_KEY

mkdir -p data/mcp_files data/chroma data/theory data/experiments/configs log

docker compose -f docker/docker-compose.yml up --build
```

打开 http://localhost:8000 — 服务端提供 `app/web/dist` 静态资源与 API 路由。

## 配置说明

| 机制 | 用途 |
|------|------|
| `env_file: ../conf/.env` | 从 conf 目录加载密钥与环境变量 |
| compose 中的 `environment:` | 容器内数据卷路径 |
| `../data:/repo/data` | 持久化 sessions.db、MCP 文件、Chroma |
| `../log:/repo/log` | 应用日志 app.log |
| `../conf:/repo/conf:ro` | MCP JSON 配置 |

推荐的容器内路径（compose 中自动设置）：

- `SESSION_DB_PATH=/repo/data/sessions.db`
- `MCP_ALLOWED_DIRS=/repo/data/mcp_files:/repo/data/theory:/repo/data/experiments`
- `THEORY_WORKSPACE_PATH=/repo/data/theory`
- `EXPERIMENTS_PATH=/repo/data/experiments`
- `RAG_CHROMA_PATH=/repo/data/chroma`
- `STRUCTURED_MEMORY_AGENTS=theory,experiment,review`
- `RAG_AGENTS=literature,theory,experiment,general`
- `LOG_FORMAT=json` — 结构化日志

镜像构建时会将 `data/theory/` 种子文件与 `data/experiments/configs/` 打入镜像；运行时 `../data` 卷挂载可覆盖或持久化会话/Chroma。

详见 `conf/docker.env.example`。

## 健康检查

```bash
curl -s http://localhost:8000/health
```

Compose 与 Dockerfile 均每 30 秒探测 `/health`。

## Token 用量统计

对话轮次完成后，token 用量写入 SQLite（`sessions.db` 中的 `token_usage_events` 表）：

```bash
curl -s 'http://localhost:8000/v1/stats/tokens'
curl -s 'http://localhost:8000/v1/stats/tokens?agent_name=literature&day=2026-06-21'
```

可通过 `ENABLE_TOKEN_STATS=false` 关闭。

## Docker 中的 MCP

MCP 服务在同一容器内以 Python 子进程运行（`mcp_servers.json`），含 **numerical**（梯度/Hessian/loss landscape）。将实验日志放在 `data/experiments/logs/`，理论笔记放在 `data/theory/lemmas/`，容器内路径为 `/repo/data/...`。

无需单独的 Chroma 服务 — 应用使用 `data/chroma` 下的 Chroma `PersistentClient`。

## 仅构建

```bash
docker compose --progress=plain -f docker/docker-compose.yml build
```

默认使用 `chroma_default` 嵌入，并安装 `pypdf`（`pip install ".[pdf]"`）以支持 PDF 入库。若需 `RAG_EMBEDDING_PROVIDER=sentence_transformers`：

```bash
INSTALL_RAG_EXTRA=1 docker compose --progress=plain -f docker/docker-compose.yml build
```

## 停止

```bash
docker compose -f docker/docker-compose.yml down
```

`data/` 中的数据会保留在宿主机卷上。

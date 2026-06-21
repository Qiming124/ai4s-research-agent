# Task 07 — Docker 与可观测性

验证容器交付、结构化日志与 token 用量聚合。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

`.env` 含有效 `DEEPSEEK_API_KEY` 用于在线冒烟（可选）。

## 自动化测试

```bash
pytest tests/ -q
pytest tests/test_observability.py -q
```

预期：**84 passed**（含 6 个可观测性测试）。

## 新增组件（Task 7）

| 组件 | 路径 |
|------|------|
| 结构化日志 | `server/observability/structured.py`、`middleware.py`、`context.py` |
| Token 用量存储 | `server/observability/token_usage.py`（SQLite `token_usage_events`） |
| 统计 API | `GET /v1/stats/tokens` — `server/api/stats.py` |
| 配置 | `LOG_FORMAT`、`ENABLE_TOKEN_STATS` 于 `server/config.py`、`.env.example` |
| Docker | `docker/Dockerfile`、`docker/docker-compose.yml`、`docker/README.md` |
| MCP 子进程修复 | `server/mcp/__init__.py` 延迟导入 |

## 结构化日志字段

当 `LOG_FORMAT=json` 时，每条日志为 JSON，含：

- `request_id` — 来自 `X-Request-ID` 请求头或自动生成（middleware）
- `session_id`、`agent_name` — 对话轮次中设置
- `tool_name`、`latency_ms` — MCP 工具调用（`tool_call_complete` / `tool_call_error`）
- HTTP 事件：`http_request_start`、`http_request_complete`

## Token 统计 API

```bash
curl -s http://127.0.0.1:8000/v1/stats/tokens
curl -s 'http://127.0.0.1:8000/v1/stats/tokens?session_id=<uuid>&agent_name=general'
curl -s 'http://127.0.0.1:8000/v1/stats/tokens?day=2026-06-21'
```

关闭持久化：`ENABLE_TOKEN_STATS=false`。

## Docker 快速启动

```bash
cp .env.example .env   # 设置 DEEPSEEK_API_KEY
mkdir -p data/mcp_files data/chroma

docker compose -f docker/docker-compose.yml up --build
```

- UI + API：http://localhost:8000
- 健康检查：`curl -s http://localhost:8000/health`
- 卷：`data/` → sessions.db、mcp_files、chroma

仅构建：

```bash
docker compose -f docker/docker-compose.yml build
```

## Docker 构建冒烟（Task 7 执行记录）

| 检查项 | 结果 |
|--------|------|
| `pytest tests/ -q` | **PASS** — 84 passed |
| `docker compose ... build` | **SKIP** — CI/沙箱无 Docker daemon（缺少 `/var/run/docker.sock`） |

本地安装 Docker 后请重新执行构建。

## 不在范围内（Task 8）

- Web 三栏布局、工具时间线 UI、RAG 管理 UI、Playwright E2E

## Task 8（p7-web）阻塞项 / 说明

- Token 统计 API（`/v1/stats/tokens`）已就绪，可供顶栏 token 用量组件使用
- 结构化日志含 `agent_name`、`tool_name`、`latency_ms` — SSE 工具时间线应对齐相同字段名
- Docker 镜像提供构建后的 `web/dist`；Task 8 UI 变更需 `docker compose up --build` 刷新
- 客户端可用 `X-Request-ID` 请求头做调试关联
- RAG 文档 API（`/v1/documents`）已存在，尚无 Web 管理 UI — Task 8 交付项

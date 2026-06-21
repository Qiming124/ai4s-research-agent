---
name: Task 07 — Docker 与可观测性
task_id: p6-docker
status: completed
---

# Task 07：Dockerfile + docker-compose + 结构化日志 + token 用量统计

## 目标

容器化全栈（web 构建 + Python 应用），增加结构化请求/工具日志，并在 SQLite 中持久化 token 用量聚合。

## 前置条件

- [x] Task 1–6 在 `dev`：LangChain、MCP、多 Agent、RAG，Chroma 于 `./data/chroma`
- [x] 仅在 `dev` 工作，不 push 远程

## 步骤

### Step 1 — 结构化日志

1. `server/observability/context.py` — ContextVars：`request_id`、`session_id`、`agent_name`
2. `server/observability/structured.py` — JSON 日志 formatter + `log_event()` 辅助
3. `server/observability/middleware.py` — FastAPI middleware：分配 `X-Request-ID`，记录 HTTP 延迟
4. `server/config.py` — `LOG_FORMAT=text|json`（默认 `text`；Docker 用 `json`）
5. 集成：`setup_logging`、`main.py` middleware、`mcp/client.call_tool` 工具延迟日志

### Step 2 — Token 用量聚合

1. `server/observability/token_usage.py` — sessions.db 中 SQLite 表 `token_usage_events`
2. 从 agent done 处理器调用 `record_token_usage(session_id, agent_name, usage)`
3. `server/api/stats.py` — `GET /v1/stats/tokens`（按 session/agent/day 过滤）
4. `shared/schemas.py` 中 schema

### Step 3 — Docker 交付

1. `docker/Dockerfile` — 多阶段：Node 20 构建 web + Python 3.12 slim 运行时
2. `docker/docker-compose.yml` — app 服务，`env_file: ../.env`，卷 `../data:/app/data`
3. `docker/.env.example` — Docker 默认（路径、LOG_FORMAT=json）
4. `docker/README.md` — 构建/运行/健康检查说明
5. `.dockerignore` — 排除 `.venv`、`node_modules`、git、缓存

### Step 4 — 测试 + benchmark + 计划更新

1. `tests/test_observability.py` — context、token store、stats API、middleware header
2. `pytest tests/ -q` + curl 冒烟
3. `benchmarks/task-07-docker.md`
4. 在 `dev` 上逻辑提交
5. 主计划标记 `p6-docker` completed

## 不在范围内（Task 8）

- Web 三栏布局、工具时间线 UI、RAG 管理 UI、Playwright E2E

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 计划文件 | done | 本文件 |
| 结构化日志 | done | JSON formatter、middleware、MCP 工具延迟 |
| Token 统计 | done | SQLite 表 + `/v1/stats/tokens` |
| Docker | done | Dockerfile、compose、README；构建跳过（无 daemon） |
| MCP 子进程修复 | done | `server/mcp/__init__.py` 延迟导入 |
| 测试 + benchmark | done | 84 passed，benchmarks/task-07-docker.md |

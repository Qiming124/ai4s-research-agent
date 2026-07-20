# AI4S 科研辅助 Agent

面向「深度学习损失函数极小值理论」研究的 AI4S 智能体：对话、MCP 工具、多 Agent 路由、RAG 记忆、课题 / Campaign、验证账本、Docker 部署。

**当前版本**：**v2.2**（分支 `v2.2`）  
**文档索引**：[`doc/README.md`](doc/README.md) · **源码阅读顺序** [`doc/CODE_READING_ORDER.md`](doc/CODE_READING_ORDER.md) · API 清单 [`doc/API-COVERAGE.md`](doc/API-COVERAGE.md)（**67** 端点）· 全路径 [`doc/API-ROUTES.md`](doc/API-ROUTES.md) · 量化 [`doc/API-QUANT-TEST-RESULTS.md`](doc/API-QUANT-TEST-RESULTS.md) · 数据约定 [`doc/DATA.md`](doc/DATA.md) · 已知问题 [`doc/KNOWN_ISSUES.md`](doc/KNOWN_ISSUES.md)

### 当前能力（v2.2）

| 模块 | 说明 |
|------|------|
| 对话与编排 | DeepSeek 流式 reasoning + content（SSE）；`legacy` / `langgraph` 多 Agent |
| 多 Agent | general / theory / experiment / literature / **review** / **counterexample** |
| MCP | web_search / arxiv / filesystem / sympy / rag / **numerical** |
| 课题工作台 | Project、任务看板、会话联动；可整包删除课题（默认课题除外）；Tabs：文献/理论/验证/图谱/实验/导出；Web 支持对话/科研/完整界面版本 |
| Campaign | S0–S8 Supervisor；SSE `campaign_update` / `artifact_saved` |
| 验证闭环 | Claim → SymPy / 数值 / Torch → 验证账本与仪表盘 |
| 记忆 | L1–L4；假设 DAG；书目 BibTeX（后端/LaTeX 导出；Web 书目面板已移除）；理论工作区在线编辑 |
| 文献 | PDF/DOCX/arXiv 入库 + RAG |
| 导出 | preview / polish / **md** / latex / docx / pdf；对话区「AI润色提示词」与导出预设共用（arXiv 短文/定理汇编/摘要页/实验报告）；PDF 公式 Unicode 规范化；DOCX 预处理；本地实验室 `data/export_test_lab/` |
| 可观测 | Token、`/v1/observability/*`、Agent 质量面板 |
| 测试 | `tests/api/` 冒烟 + 分域；Playwright 三场景（课题/文献/导出） |
| Docker | 单镜像前端 + API（理论种子打包问题见 KNOWN_ISSUES C1） |

历史里程碑：`v0.4` 底座 · `v1.x` 产业化 · `v2.0`/`v2.1` Campaign 与渲染加固 → **`v2.2`** 当前线。

---

## 项目架构

### 分层结构

```
┌─────────────────────────────────────────┐
│  Transport 层（SSE 流式推送）             │
│  app/client/cli.py  /  app/web/src/     │
├─────────────────────────────────────────┤
│  Route 层（FastAPI · 15 域 API）         │
│  app/server/api/*.py                     │
├─────────────────────────────────────────┤
│  Agent 层（业务编排 + Campaign）          │
│  app/server/agents/ · graph/             │
├──────────────┬──────────────────────────┤
│  Memory 层    │  LLM + MCP               │
│  session/rag/ │  client.py + mcp/        │
│  structured/  │                          │
│  projects/    │                          │
├──────────────┴──────────────────────────┤
│  Config：conf/.env → Settings            │
│  Schema：app/shared/schemas.py           │
└─────────────────────────────────────────┘
```

> **路径说明**：Python 包名仍为 `server`、`client`、`shared`（代码在 `app/` 下）。启动 uvicorn 时需加 `--app-dir app`。

### 一次对话的完整链路

```
用户输入 → CLI / Web → POST /v1/chat/stream (SSE)
  → app/server/api/chat.py        （路由：校验 + 序列化）
    → agents / graph              （编排：历史 → MCP/RAG → LLM）
      → app/server/llm/client.py  （DeepSeek：流式 reasoning + content）
    → memory + verification       （写回会话 / 账本 / Campaign）
  → SSE 事件流 → 客户端实时渲染（可自动切工作台 Tab）
```

### 目录布局

```
agent/
├── README.md              # 项目总览（根目录保留）
├── app/                   # 全部应用代码
│   ├── server/            # FastAPI 后端
│   ├── client/            # CLI
│   ├── shared/            # schemas + paths
│   └── web/               # Vite + React 前端
├── conf/                  # .env 模板、mcp_servers.json 等
├── doc/                   # 技术文档
├── log/                   # 运行时日志 app.log
├── data/                  # 运行时 DB/chroma + 理论种子（见 doc/DATA.md）
└── docker/                # Dockerfile / compose
```

### 主要模块

| 路径 | 职责 |
|------|------|
| `app/shared/schemas.py` | 请求/响应/流式 chunk |
| `app/server/config.py` | Settings（`conf/.env`） |
| `app/server/llm/` | DeepSeek 客户端与 prompt |
| `app/server/memory/` | 会话、RAG、L4、课题、Campaign |
| `app/server/agents/` · `graph/` | Agent 与 LangGraph / Supervisor |
| `app/server/api/` | HTTP 路由与 SSE（67 端点） |
| `app/server/main.py` | FastAPI 入口 |
| `app/client/cli.py` | 终端 CLI |
| `app/web/` | React 科研工作台 |

---

## 分支管理

| 分支 | 用途 |
|------|------|
| **`v2.2`** | **当前开发/发布线（推荐）** |
| `v2.1` / `v2.0` | 里程碑存档 |
| `dev` | 历史开发汇合线 |
| `master` | 稳定发布线 |
| `v0.1`–`v1.2` | 早期里程碑存档 |

```bash
git checkout v2.2
```

---

## 代码阅读顺序

| 序号 | 文件 | 作用 |
|------|------|------|
| 1 | `app/shared/schemas.py` | 数据结构 |
| 2 | `app/server/config.py` | Settings |
| 3 | `app/server/llm/` + `memory/` | LLM 与记忆 |
| 4 | `app/server/agents/` + `graph/` | 编排与流水线 |
| 5 | `app/server/api/` + `main.py` | HTTP / SSE |
| 6 | `app/web/src/` | 科研工作台 UI |
| 7 | `doc/API-COVERAGE.md` + `doc/API-ROUTES.md` | 端点清单与全路径链路 |

---

## 环境准备

**要求**：Python 3.11+

```bash
cd /path/to/agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp conf/.env.example conf/.env
# 编辑 conf/.env，填入 DEEPSEEK_API_KEY
```

> `conf/.env.example` 为**演示配置**（MCP/RAG/langgraph 开启）。代码 `Settings` 默认更保守。详见 [`doc/ENV.md`](doc/ENV.md)。

密钥获取：[DeepSeek 开放平台](https://platform.deepseek.com/)。`conf/.env` 已 gitignore；公网部署须加鉴权（见 KNOWN_ISSUES C2）。

---

## 配置说明（conf/.env）

完整表：[`doc/ENV.md`](doc/ENV.md)。

| 变量 | 代码默认 | 演示（.env.example） | 说明 |
|------|----------|----------------------|------|
| `DEEPSEEK_API_KEY` | （必填） | 占位符 | API 密钥 |
| `ENABLE_MCP` | `false` | `true` | MCP 工具 |
| `ORCHESTRATION_BACKEND` | `legacy` | `langgraph` | 编排 |
| `ENABLE_RAG` | `false` | `true` | 向量检索 |
| `RESEARCH_PIPELINE_MODE` | `single` | `single` | `auto` 多跳 |
| `ENABLE_CLOUD_SYNC` | `false` | `false` | 云端元数据同步 |
| `THEORY_WORKSPACE_PATH` | `./data/theory` | 同左 | 理论种子 |

---

## 快速启动

### 后端

```bash
source .venv/bin/activate
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir app
```

### CLI

```bash
python -m client.cli --mode math --agent theory
python -m client.cli --agent counterexample
```

### Web

```bash
cd app/web && npm install && npm run dev   # http://localhost:5173
# 生产：npm run build 后由 FastAPI 托管 dist
```

### 部署

[`doc/docker.md`](doc/docker.md) · [`doc/DEPLOY.md`](doc/DEPLOY.md) · Nginx SSE 须 `proxy_buffering off`。

---

## API 参考

[`doc/API-COVERAGE.md`](doc/API-COVERAGE.md)（67 端点）· [`doc/API-ROUTES.md`](doc/API-ROUTES.md)（全路径链路）· [`doc/API.md`](doc/API.md) · `GET /docs`

```bash
curl http://127.0.0.1:8000/health
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"二次损失临界点","session_id":"test","mode":"math","agent":"theory"}'
```

SSE：`meta` → `pipeline_stage` / `campaign_update` → `workflow_step` → `tool_call_*` → `reasoning` → `content` → `verification_result` / `numerical_verification_result` → `done`

### 理论验证本地重跑

```bash
# 单元 / 回归
pytest tests/test_theory_pipeline.py tests/test_research_supervisor.py \
  tests/test_verification_executor_async.py tests/derivation_benchmark/ -q

# 数值 Claim（主循环 await，成功 status=completed + overall_passed）
curl -s -X POST http://127.0.0.1:8000/v1/verification/run \
  -H "Content-Type: application/json" \
  -d '{"claim":{"expression":"x0**2 + x1**2","point":"0,0","variables":"x0,x1","expected":{"classification":"local_minimum"},"tier_hint":"numerical"},"session_id":"demo-v"}'

# 实验配置 quadratic_minimum（须 await run_config_async，勿嵌套 event loop）
curl -s -X POST http://127.0.0.1:8000/v1/experiments/runs \
  -H "Content-Type: application/json" \
  -d '{"config_path":"quadratic_minimum.yaml"}'
```

成功时实验日志顶层为 `status: completed`，分层里 numerical 为 `pass`；Campaign S5 按 `overall_passed` / `completed` 判定 `quadratic_pass`，不再误把成功当成失败。

---

## 调试指南

| 现象 | 排查 |
|------|------|
| `ValidationError` | 配置 `conf/.env` |
| Connection refused | 先启动 uvicorn |
| 重启丢会话 | `SESSION_STORE_BACKEND=sqlite` |
| 公式异常 / 橙色原文乱码 | 优先 `cd app/web && npm run test:math`；见 `doc/web.md`。导出 PDF 公式/`→p` 乱码：跑 `scripts/export_test_lab.py`，看 `data/export_test_lab/reports/` |
| 找不到 `web/` | 路径为 `app/web`，后端加 `--app-dir app` |
| Docker 无理论 md | KNOWN_ISSUES C1（`.dockerignore`） |
| 实验 API 报 event loop / 整站卡死 | 须 `await run_config_async`；禁止在 async 路由里 `new_event_loop` 调 MCP |
| 数值验证「失败」但无原因 | 看 `tiers.numerical.reason`；脏 LaTeX 不会再当表达式 |

---

## 扩展指引

新建 Agent → 白名单注册；流水线见 `graph/`；MCP 见 [`doc/mcp-config.md`](doc/mcp-config.md) · [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md)。

---

## 依赖与许可证

见 `pyproject.toml`（包版本 **2.2.0**）。MIT；请遵守 DeepSeek API 使用条款。

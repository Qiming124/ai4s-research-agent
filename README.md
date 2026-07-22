# AI4S 理论侧科研助手

面向「**用深度学习解决科学问题**」的 **理论侧多智能体**：协助检索并阅读文献、理论推导与形式化、给出实验建议与下一步方向、解读用户提交的实验数据。

**示范子集**：损失函数局部极小 / 优化理论等为课题种子与能力子集，**不是**唯一领域。  
**不做**：在系统内复现全流程科研、部署/代训模型、或把大规模数值实验实跑当作核心能力。

**当前版本**：**v2.2**（分支 `v2.2`）  
**产品愿景（下期蓝图）**：[`doc/PRODUCT-VISION.md`](doc/PRODUCT-VISION.md)  
**文档索引**：[`doc/README.md`](doc/README.md) · **源码阅读顺序** [`doc/CODE_READING_ORDER.md`](doc/CODE_READING_ORDER.md) · **API 测试实验室** [`doc/API-LAB.md`](doc/API-LAB.md) · API 清单 [`doc/API-COVERAGE.md`](doc/API-COVERAGE.md)（**65** 端点）· 全路径 [`doc/API-ROUTES.md`](doc/API-ROUTES.md) · 量化 [`doc/API-QUANT-TEST-RESULTS.md`](doc/API-QUANT-TEST-RESULTS.md) · **功能验收** [`doc/acceptance/ACCEPTANCE-TEST-PLAN.md`](doc/acceptance/ACCEPTANCE-TEST-PLAN.md) / [报告](doc/acceptance/ACCEPTANCE-REPORT.md) · 数据约定 [`doc/DATA.md`](doc/DATA.md) · 已知问题 [`doc/KNOWN_ISSUES.md`](doc/KNOWN_ISSUES.md)

### 能力边界（v2.2）

| 做 | 不做（主叙事） |
|----|----------------|
| 文献检索与方法提炼；理论推导、符号/假设一致性、审稿清单 | 完整科研工作流复现 |
| PDF/DOCX/arXiv 入库 + RAG（自动入库增强为后续） | Torch / 宽度扫描等「代跑训练」 |
| 实验建议、实验计划、缺数诊断、下一步方向 | 以 numerical MCP / Jupyter 实跑为核心卖点 |
| 用户提交指标/日志后的对照理论解读（JSON / Excel / CSV） | 云端训模型或代部署推理服务 |

### 当前能力一览

| 模块 | 说明 |
|------|------|
| 对话与编排 | DeepSeek 流式 reasoning + content（SSE）；`legacy` / `langgraph` 多 Agent |
| 多 Agent | general / theory / **experiment（实验顾问）** / literature / review / counterexample |
| MCP | web_search / arxiv / filesystem / sympy / rag（numerical 为可选辅助，非代跑实验主路径） |
| 课题工作台 | Project、会话联动；Tabs：文献 / 理论（定理库·推导迹）/ 产出；对话版 / 科研版；左右侧栏可用 « / » 收起 |
| 记忆 | L1–L4；定理库 CRUD/导入；符号与假设经种子注入模型（无工作区/DAG HTTP） |
| 文献 | 检索 + 方法提炼；手动入库 + RAG |
| 导出 | preview / polish / md / latex / docx / pdf；「AI润色提示词」（模板/案例见 `conf/prompt/*.json`） |
| 可观测 | Token、`/v1/observability/*`、Agent 质量面板 |
| Docker | 单镜像前端 + API（理论种子打包问题见 KNOWN_ISSUES C1） |

历史里程碑：`v0.4` 底座 · `v1.x` 产业化 · `v2.0`/`v2.1` → **`v2.2`** AI4S 理论侧多智能体（已移除 Campaign S0–S8；领域从窄局部极小上提为 DL-for-Science 理论侧）。

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
│  Agent 层（理论侧多角色编排）             │
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
    → memory                      （写回会话 / L4 / 课题）
  → SSE 事件流 → 客户端实时渲染
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
| `app/server/memory/` | 会话、RAG、L4、课题 |
| `app/server/agents/` · `graph/` | 理论侧 Agent 与 LangGraph 路由 |
| `app/server/api/` | HTTP 路由与 SSE（65 端点） |
| `app/server/main.py` | FastAPI 入口 |
| `app/client/cli.py` | 终端 CLI |
| `app/web/` | React 理论侧工作台 |

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
| 6 | `app/web/src/` | 理论侧工作台 UI |
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

[`doc/API-COVERAGE.md`](doc/API-COVERAGE.md)（65 端点）· [`doc/API-ROUTES.md`](doc/API-ROUTES.md)（全路径链路）· [`doc/API.md`](doc/API.md) · `GET /docs`（Swagger：中文接口说明、字段注解与样例值）· 前端 `#/api-lab` 同步读取 `/openapi.json`

```bash
curl http://127.0.0.1:8000/health
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"二次损失临界点","session_id":"test","mode":"math","agent":"theory"}'
```

SSE：`meta` → `workflow_step` → `tool_call_*` → `reasoning` → `content` → `artifact_saved` → `done`（验证类事件可选；`pipeline_stage` / `campaign_update` 仅为 schema 兼容名，主路径不再产生）

推荐对话示例：理论推导用 `agent=theory`；文献方法提炼用 `literature`；实验计划与读数用 `experiment`。

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

新建 Agent → 白名单注册；编排见 `graph/`；MCP 见 [`doc/mcp-config.md`](doc/mcp-config.md) · [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) · 产品蓝图 [`doc/PRODUCT-VISION.md`](doc/PRODUCT-VISION.md)。

---

## 依赖与许可证

见 `pyproject.toml`（包版本 **2.2.0**）。MIT；请遵守 DeepSeek API 使用条款。

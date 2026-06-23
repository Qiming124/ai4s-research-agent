# AI4S 科研辅助 Agent

面向「深度学习损失函数极小值理论」研究的 AI4S 智能体：对话、MCP 工具、多 Agent 路由、RAG 记忆、Docker 部署。

**文档索引**：[`doc/README.md`](doc/README.md)（架构、API、环境变量、部署）

**当前能力概览**：

| 模块 | 说明 |
|------|------|
| 对话 | DeepSeek V4 Pro 流式 reasoning + content（SSE） |
| L2 会话 | SQLite 持久化，含 reasoning、tool_calls |
| L1 工作记忆 | 历史截断与可选 LLM 摘要 |
| MCP | web_search / arxiv / filesystem（stdio） |
| 多 Agent | `ORCHESTRATION_BACKEND=langgraph` 时 Supervisor 路由 |
| RAG | Chroma 向量库 + `/v1/documents` |
| Web | 三栏 UI、KaTeX 公式、会话列表 |
| Docker | 单镜像含前端构建产物与 API |

---

## 项目架构

### 分层结构

```
┌─────────────────────────────────────────┐
│  Transport 层（SSE 流式推送）             │
│  client/cli.py  /  web/src/              │
├─────────────────────────────────────────┤
│  Route 层（FastAPI HTTP 端点）            │
│  server/api/chat.py                      │
├─────────────────────────────────────────┤
│  Agent 层（业务编排）                      │
│  server/agents/base.py                   │
├──────────────┬──────────────────────────┤
│  Memory 层    │  LLM 层                   │
│  session.py   │  client.py + prompts.py  │
├──────────────┴──────────────────────────┤
│  Config 层（.env → Settings 单例）        │
│  server/config.py                        │
├─────────────────────────────────────────┤
│  Schema 层（数据模型）                     │
│  shared/schemas.py                       │
└─────────────────────────────────────────┘
```

### 一次对话的完整链路

```
用户输入 → CLI / Web → POST /v1/chat/stream (SSE)
  → server/api/chat.py        （路由：校验 + 序列化）
    → server/agents/base.py   （Agent：读历史 → 拼消息 → 调 LLM）
      → server/llm/client.py  （DeepSeek API：流式 reasoning + content）
    → server/memory/session.py（写回 user + assistant 消息）
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
├── data/                  # sessions.db、chroma、mcp_files
└── docker/                # Dockerfile / compose
```

Python 包名仍为 `server`、`client`、`shared`（位于 `app/` 下），import 写法不变。

### 主要模块

| 路径 | 职责 |
|------|------|
| `app/shared/schemas.py` | 请求/响应/流式 chunk 数据结构 |
| `app/shared/paths.py` | 仓库根、conf、log、data 路径常量 |
| `app/server/config.py` | 从 `conf/.env` 加载配置 |
| `app/server/llm/` | DeepSeek 客户端与 prompt |
| `app/server/memory/` | 会话存储（SQLite / 内存） |
| `app/server/agents/` | Agent 编排与 tool loop |
| `app/server/api/` | HTTP 路由与 SSE |
| `app/server/main.py` | FastAPI 入口、静态文件托管 |
| `app/client/cli.py` | 终端 CLI |
| `app/web/` | React 聊天 UI |

---

## 分支管理

| 分支 | 用途 |
|------|------|
| `master` | 主开发分支，最新功能 |
| `v0.1` | **当前分支**——Phase 1 中间状态存档（可对话 Agent + CLI + Web + 完整中文注释） |

切换分支：

```bash
git checkout master   # 最新开发版
git checkout v0.1     # Phase 1 存档版
```

---

## 代码阅读顺序

按依赖关系从底层数据结构到顶层入口，建议逐文件阅读：

| 序号 | 文件 | 作用 |
|------|------|------|
| 1 | `app/shared/schemas.py` | 所有数据结构的定义 |
| 2 | `app/server/llm/prompts.py` | System Prompt 常量 |
| 3 | `app/server/config.py` | Settings — 从 conf/.env 加载 |
| 4 | `app/server/memory/session.py` | SessionStore |
| 5 | `app/server/llm/client.py` | DeepSeekClient |
| 6 | `app/server/agents/base.py` | BaseAgent + GeneralAgent |
| 7 | `app/server/api/chat.py` | HTTP 端点与 SSE |
| 8 | `app/server/main.py` | FastAPI 入口 |
| 9 | `app/client/cli.py` | 终端客户端 |
| 10 | `app/web/src/` | React 前端（可选） |

---

## 环境准备

**要求**：Python 3.11+

```bash
# 1. 进入项目目录
cd /path/to/agent

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装项目依赖
pip install -e .

# 4. 配置 API Key
cp conf/.env.example conf/.env
# 编辑 conf/.env，填入 DEEPSEEK_API_KEY
```

### 获取 DeepSeek API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册/登录 → API Keys → 创建密钥
3. 将密钥写入 `conf/.env` 的 `DEEPSEEK_API_KEY=sk-...`

### 安全提示

- `conf/.env` 包含真实密钥，已被 `.gitignore` 排除，**永远不会**被提交到 Git
- `conf/.env.example` 是**公开模板**，值固定为占位符 `sk-your-api-key-here`，可以安全提交
- 如果密钥曾泄露，请去 DeepSeek 控制台删除旧 Key 并生成新 Key

---

## 配置说明（conf/.env）

完整变量表见 [`doc/ENV.md`](doc/ENV.md)。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | （必填） | API 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `MODEL` | `deepseek-v4-pro` | 模型 ID |
| `MAX_TOKENS` | `384000` | 最大输出 token |
| `REASONING_EFFORT` | `max` | 推理强度：`high` 或 `max` |
| `LOG_LEVEL` | `INFO` | `DEBUG` 可打印 LLM 请求摘要 |
| `LOG_FORMAT` | `text` | Docker 建议 `json` |
| `ENABLE_TOKEN_STATS` | `true` | Token 用量写入 SQLite |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `SESSION_STORE_BACKEND` | `sqlite` | `sqlite` 或 `memory` |
| `SESSION_DB_PATH` | `./data/sessions.db` | SQLite 路径 |
| `MAX_HISTORY_MESSAGES` | `0` | L1 截断条数，`0` 不限制 |
| `ENABLE_HISTORY_SUMMARY` | `false` | 截断时 LLM 摘要 |
| `ENABLE_MCP` | `false` | **启用 MCP 工具** |
| `ORCHESTRATION_BACKEND` | `legacy` | `legacy` 或 `langgraph` |
| `ENABLE_RAG` | `false` | 启用 RAG 向量检索 |

MCP、RAG 其余变量见 `conf/.env.example` 与 [`doc/mcp-config.md`](doc/mcp-config.md)。

## Phase 2A 能力清单

| 能力 | 说明 |
|------|------|
| L2 SQLite 持久化 | 重启后会话不丢失（`SESSION_STORE_BACKEND=sqlite`） |
| L1 历史截断 | `MAX_HISTORY_MESSAGES>0` 时只向 LLM 发送最近 N 条 |
| L1 可选 LLM 摘要 | `ENABLE_HISTORY_SUMMARY=true` 时压缩被截断的旧消息 |
| reasoning 持久化 | assistant 思考过程写入 DB，Web 刷新后可恢复 |
| Web 历史恢复 | 页面加载时 `GET /v1/sessions/{id}` 回填 |
| Web/CLI Math 模式 | 请求 `mode=math` 使用数学推导 prompt |
| Web/CLI L1 策略 | 客户端可覆盖 `max_history_messages` / `enable_history_summary` |
| SSE agent_name | 流式 meta/done 事件携带 Agent 名称 |

**L1 历史策略（客户端）**

- 请求体字段 `max_history_messages`、`enable_history_summary` 为 `null`/省略时，使用服务端 `.env` 默认值
- Web：顶栏下方「历史策略」区域；勾选「服务端默认」则不发送上述字段
- CLI：`--max-history N`、`--history-summary on|off|default`

---

## 快速启动

### 后端（Python Server）

```bash
source .venv/bin/activate

# 开发模式（带热重载）
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir app

# 生产模式（配合 Nginx，无 reload 低 CPU）
uvicorn server.main:app --host 127.0.0.1 --port 8000 --app-dir app
```

启动后会打印配置摘要（API Key 脱敏）：

```
AI4S Research Agent Server 启动
  模型: deepseek-v4-pro
  推理强度: max
  API Key: sk-***xxxx
```

### 终端 CLI 客户端

```bash
source .venv/bin/activate
python -m client.cli
python -m client.cli --mode math          # 数学推导模式
python -m client.cli --max-history 20     # L1 保留最近 20 条（覆盖 .env）
python -m client.cli --history-summary on # 截断时 LLM 摘要旧消息
python -m client.cli --no-show-reasoning  # 隐藏思考过程
python -m client.cli --session my-work    # 固定会话 ID
# 或：research-agent-cli
```

### Web 前端

**环境要求**：WSL 内使用 Linux 版 Node.js。

```bash
sudo apt install nodejs npm

# 开发模式
cd app/web && npm install && npm run dev   # → http://localhost:5173

# 生产模式（与 API 同端口 8000）
cd app/web && npm install && npm run build
cd ../../ && uvicorn server.main:app --host 0.0.0.0 --port 8000 --app-dir app
# → http://127.0.0.1:8000/
```

**Web 功能（Phase 2A）**：

| 功能 | 说明 |
|------|------|
| 历史恢复 | 刷新页面后自动从 `GET /v1/sessions/{id}` 回填消息（需 `SESSION_STORE_BACKEND=sqlite`） |
| 停止生成 | 流式过程中点击「停止」，保留已生成内容 |
| 思考过程开关 | 顶栏勾选控制是否显示 ReasoningPanel，偏好存 localStorage |
| Chat / Math 模式 | 切换对话模式，请求携带 `mode` 字段（math 使用数学推导 prompt） |
| 清空会话 | 调用 `DELETE /v1/sessions/{id}` 并清空 UI |

### 生产部署

- **Docker**：见 [`doc/docker.md`](doc/docker.md) 与 [`doc/DEPLOY.md`](doc/DEPLOY.md)
- **Nginx + systemd**：见下方示例（SSE 需关闭 `proxy_buffering`）

```bash
# 1. 安装 Nginx
apt install nginx -y

# 2. 配置 Nginx 反代（80 → 127.0.0.1:8000）
cat > /etc/nginx/sites-available/ai4s << 'EOF'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_buffering off;        # SSE 必须关缓冲
        proxy_cache off;
        proxy_read_timeout 600s;    # thinking max 可能很久
    }
}
EOF
ln -sf /etc/nginx/sites-available/ai4s /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 3. 后台运行（退出终端不挂）
nohup uvicorn server.main:app --host 127.0.0.1 --port 8000 \
      > /var/log/ai4s-agent.log 2>&1 &

# 4. 用 systemd 守护（推荐生产环境）
cat > /etc/systemd/system/ai4s-agent.service << 'EOF'
[Unit]
Description=AI4S Research Agent
After=network.target
[Service]
Type=simple
WorkingDirectory=/root/ai4s-research-agent
ExecStart=/usr/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000 --app-dir app
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now ai4s-agent
```

---

## API 参考

详见 [`doc/API.md`](doc/API.md)。

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok","model":"deepseek-v4-pro","reasoning_effort":"max"}
```

### POST /v1/chat（非流式）

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"什么是损失函数的极小值？","session_id":"test"}'
```

### POST /v1/chat/stream（SSE 流式）

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"简要解释 SGD 收敛性","session_id":"test","mode":"math"}'
```

请求体可选字段：`session_id`、`system_prompt`、`mode`（`chat` 或 `math`，默认 `chat`）。

SSE 事件 type：`meta`（会话ID）→ `reasoning` → `content` → `done`（结束）

### GET /v1/sessions/{id} | DELETE /v1/sessions/{id}

查询/清空会话历史。

---

## CLI 命令

```bash
python -m client.cli --server http://127.0.0.1:8000
python -m client.cli --session my-work        # 固定会话 ID
python -m client.cli --no-show-reasoning      # 隐藏推理过程
```

交互命令：`/clear`（清空会话）| `/history`（查看历史）| `exit` / `quit`（退出）| 行末 `\` 回车（多行输入）

---

## 调试指南

| 现象 | 可能原因 | 排查步骤 |
|------|----------|----------|
| 启动报 `ValidationError` | `conf/.env` 未配置 | `cp conf/.env.example conf/.env` 并填入密钥 |
| `401 Unauthorized` | API Key 无效 | 检查 DeepSeek 控制台 |
| CLI `Connection refused` | Server 未启动 | 先运行 uvicorn |
| SSE 无输出后中断 | 网络/API 限流 | `LOG_LEVEL=DEBUG` 查日志 |
| 多轮对话无上下文 | session_id 不一致 | CLI 用 `--session` 固定 |
| 重启后会话丢失 | `SESSION_STORE_BACKEND=memory` | 改为 `sqlite`（默认）；或确认 `data/sessions.db` 存在 |
| reasoning 为空 | 配置问题 | 确认 `REASONING_EFFORT=max` |
| 部署后访问白屏 | 浏览器缓存 | Ctrl+Shift+R 硬刷新 |
| Nginx 访问 502 | 后端未启动 | `systemctl status ai4s-agent` |

---

## Phase 2 扩展指引

1. 在 `server/agents/` 继承 `BaseAgent` 新建 Agent（TheoryAgent / ExperimentAgent / LiteratureAgent）
2. 定义专用 `system_prompt`
3. 实现 `async def run(...)` 方法
4. 通过 LangGraph router 按用户意图分发

```python
class TheoryAgent(BaseAgent):
    name = "theory"
    system_prompt = "..."

    async def run(self, message, session_id, *, system_prompt_override=None):
        ...
```

---

## 依赖

见 `pyproject.toml`。核心：`fastapi`、`uvicorn`、`openai`、`pydantic-settings`、`httpx`、`httpx-sse`、`rich`、`prompt-toolkit`。

前端：`react`、`vite`、`react-markdown`、`remark-gfm`、`rehype-katex`、`rehype-highlight`。

---

## 许可证

MIT（科研辅助工具，请遵守 DeepSeek API 使用条款）。

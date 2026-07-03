# 环境变量说明

配置文件：`conf/.env`（从 `conf/.env.example` 复制）。  
加载逻辑：`app/server/config.py` 中的 `Settings`，大小写不敏感。

## 必填

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥，不可为占位符 `sk-your-api-key-here` |

## LLM

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 基础 URL |
| `MODEL` | `deepseek-v4-pro` | 模型 ID |
| `MAX_TOKENS` | `384000` | 单次最大输出 token |
| `REASONING_EFFORT` | `max` | 推理强度：`high` 或 `max` |

## 服务与日志

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `LOG_LEVEL` | `INFO` | `DEBUG` 可打印更多 LLM 请求信息 |
| `LOG_FORMAT` | `text` | `json` 用于 Docker/日志采集 |
| `ENABLE_TOKEN_STATS` | `true` | 是否写入 token 用量到 SQLite |

## 会话存储（L2）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SESSION_STORE_BACKEND` | `sqlite` | `sqlite` 持久化 或 `memory` 内存 |
| `SESSION_DB_PATH` | `./data/sessions.db` | SQLite 数据库路径 |

## L1 工作记忆

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MAX_HISTORY_MESSAGES` | `0` | 保留最近 N 条历史；`0` 不截断 |
| `ENABLE_HISTORY_SUMMARY` | `false` | 截断时是否 LLM 摘要旧消息 |
| `HISTORY_SUMMARY_MAX_TOKENS` | `1024` | 摘要最大输出 token |

## MCP 工具

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_MCP` | `false` | **是否启用 MCP**；生产需 `true` |
| `MCP_CONFIG_PATH` | `./conf/mcp_servers.json` | MCP Server 配置路径 |
| `MCP_ALLOWED_DIRS` | `./data/mcp_files:./data/theory:./data/experiments` | filesystem MCP 可读目录（冒号分隔） |
| `MCP_MAX_TOOL_ROUNDS` | `10` | 单轮对话最大工具循环次数 |
| `MCP_TOOL_RESULT_MAX_CHARS` | `8000` | 工具结果写入上下文前最大字符 |
| `MCP_TOOL_WHITELIST` | 空 | 全局工具 glob 白名单 |
| `MCP_TOOL_WHITELIST_PATH` | 空 | JSON 白名单文件（支持按 Agent 映射） |

## Agent 编排

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORCHESTRATION_BACKEND` | `legacy` | `legacy`：仅 `GeneralAgent`；`langgraph` 或 `multi`：多 Agent Supervisor + SubAgent |
| `ROUTER_USE_LLM` | `false` | `true` 时用 LLM 做意图路由，失败时回退关键词规则 |

**说明**：多 Agent 含 general / theory / experiment / literature / **review**。设 `ORCHESTRATION_BACKEND=langgraph` 启用 Supervisor 路由。`RESEARCH_PIPELINE_MODE=auto` 时复杂问题走多跳流水线。

推荐演示配置：`ORCHESTRATION_BACKEND=langgraph`、`ENABLE_MCP=true`、`ENABLE_RAG=true`。

## 理论工作区与研究流水线（v0.4）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `THEORY_WORKSPACE_PATH` | `./data/theory` | 符号表、假设、引理种子目录 |
| `EXPERIMENTS_PATH` | `./data/experiments` | 实验配置与日志目录 |
| `RESEARCH_PIPELINE_MODE` | `single` | `auto` 启用 literature→theory→experiment→review 多跳 |
| `ENABLE_NUMERICAL_MCP` | `true` | 是否注册 numerical MCP Server |
| `GLOBAL_MEMORY_SYNC` | `true` | 启动时同步 `data/theory/lemmas/` → L4 全局记忆 |
| `PDF_INGEST_ENABLED` | `true` | 是否启用 PDF 上传解析 |

## RAG（L3）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_RAG` | `false` | 是否启用向量检索 |
| `RAG_CHROMA_PATH` | `./data/chroma` | Chroma 持久化目录 |
| `RAG_EMBEDDING_PROVIDER` | `chroma_default` | 嵌入模型提供方 |
| `RAG_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers 模型名 |
| `RAG_EMBEDDING_BASE_URL` | 空 | OpenAI 兼容 Embedding API |
| `RAG_CHUNK_SIZE` | `800` | 分块大小 |
| `RAG_CHUNK_OVERLAP` | `100` | 分块重叠 |
| `RAG_RETRIEVAL_TOP_K` | `4` | 检索返回条数 |
| `RAG_AGENTS` | `literature,theory,experiment,general` | 启用 RAG 的 Agent |
| `RAG_INDEX_MCP_FILES` | `false` | 启动时索引 MCP 目录下 md/txt |

## L4 结构化记忆

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STRUCTURED_MEMORY_AGENTS` | `theory,experiment,review` | 注入 L4 记忆的 Agent 列表 |
| `ROUTER_USE_LLM` | `false` | LLM 意图路由（失败回退规则） |
| `TAVILY_API_KEY` | 空 | Tavily 搜索 Key；web_search MCP 优先使用 |

## Docker 容器内推荐路径

Compose 会自动覆盖为容器路径（`/repo/...`）：

- `SESSION_DB_PATH=/repo/data/sessions.db`
- `MCP_ALLOWED_DIRS=/repo/data/mcp_files:/repo/data/theory:/repo/data/experiments`
- `THEORY_WORKSPACE_PATH=/repo/data/theory`
- `EXPERIMENTS_PATH=/repo/data/experiments`
- `RAG_CHROMA_PATH=/repo/data/chroma`
- `MCP_CONFIG_PATH=/repo/conf/mcp_servers.json`

镜像内不包含 `.env`，必须通过 `env_file` 或 `-e` / `--env-file` 注入。

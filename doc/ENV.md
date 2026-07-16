# 环境变量说明（v2.2）

配置文件：`conf/.env`（从 `conf/.env.example` 复制）。  
加载逻辑：`app/server/config.py` 中的 `Settings`，大小写不敏感。

> **默认值约定**：下表「代码默认」来自 `Settings` 字段默认值（未写 `.env` 时）。  
> `conf/.env.example` 是**演示配置**（开启 MCP / RAG / langgraph），与代码默认不同——复制后即可开全能力。

## 必填

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥，不可为占位符 `sk-your-api-key-here` |

## LLM

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 基础 URL |
| `MODEL` | `deepseek-v4-pro` | 模型 ID |
| `MAX_TOKENS` | `384000` | 单次最大输出 token |
| `REASONING_EFFORT` | `max` | `high` 或 `max` |

## 服务与日志

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `LOG_LEVEL` | `INFO` | `DEBUG` 可打印更多 LLM 请求信息 |
| `LOG_FORMAT` | `text` | `json` 用于 Docker/日志采集 |
| `ENABLE_TOKEN_STATS` | `true` | 是否写入 token 用量到 SQLite |

## 会话存储（L2）

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `SESSION_STORE_BACKEND` | `sqlite` | `sqlite` 或 `memory` |
| `SESSION_DB_PATH` | `./data/sessions.db` | SQLite 路径 |

## L1 工作记忆

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `MAX_HISTORY_MESSAGES` | `0` | 保留最近 N 条；`0` 不截断 |
| `ENABLE_HISTORY_SUMMARY` | `false` | 截断时是否 LLM 摘要 |
| `HISTORY_SUMMARY_MAX_TOKENS` | `1024` | 摘要最大输出 token |

## MCP 工具

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `ENABLE_MCP` | `false` | 是否启用 MCP（演示请设 `true`） |
| `MCP_CONFIG_PATH` | `./conf/mcp_servers.json` | Server 配置 |
| `MCP_ALLOWED_DIRS` | `./data/mcp_files` | filesystem 可读目录（冒号分隔）；演示建议追加 `theory`/`experiments` |
| `MCP_MAX_TOOL_ROUNDS` | `10` | 单轮最大工具循环 |
| `MCP_TOOL_RESULT_MAX_CHARS` | `8000` | 工具结果截断长度 |
| `MCP_TOOL_WHITELIST` | 空 | 全局 glob 白名单；空=不额外限制 |
| `MCP_TOOL_WHITELIST_PATH` | `./conf/mcp_tool_whitelist.json` | 按 Agent 的 JSON 白名单 |

## Agent 编排

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `ORCHESTRATION_BACKEND` | `legacy` | `legacy` 单 Agent；`langgraph`/`multi` 多 Agent（演示用 langgraph） |
| `ROUTER_USE_LLM` | `false` | `true` 时 LLM 意图路由，失败回退规则 |

多 Agent：`general` / `theory` / `experiment` / `literature` / `review` / `counterexample`。  
`RESEARCH_PIPELINE_MODE=auto` 时复杂问题走 literature→theory→experiment→review 多跳；Campaign 另见 Supervisor（S0–S8）。

## 理论 / 实验 / 流水线 / 同步

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `THEORY_WORKSPACE_PATH` | `./data/theory` | 符号表、假设、引理种子 |
| `EXPERIMENTS_PATH` | `./data/experiments` | 实验配置与日志 |
| `RESEARCH_PIPELINE_MODE` | `single` | `auto` = 多跳流水线 |
| `ENABLE_NUMERICAL_MCP` | `true` | 注册 numerical MCP |
| `GLOBAL_MEMORY_SYNC` | `true` | 启动同步 `data/theory/lemmas/` → L4 |
| `PDF_INGEST_ENABLED` | `true` | PDF 上传解析 |
| `ENABLE_CLOUD_SYNC` | `false` | 可选云端元数据同步（不含推导正文） |
| `TAVILY_API_KEY` | 空 | web_search 优先 Tavily（国内推荐） |

## RAG（L3）

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `ENABLE_RAG` | `false` | 向量检索（演示请设 `true`） |
| `RAG_CHROMA_PATH` | `./data/chroma` | Chroma 目录 |
| `RAG_EMBEDDING_PROVIDER` | `chroma_default` | `chroma_default` / `sentence_transformers` / `openai` / `test` |
| `RAG_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers 模型名 |
| `RAG_EMBEDDING_BASE_URL` | 空 | OpenAI 兼容 Embedding；空则用 DeepSeek Base |
| `RAG_CHUNK_SIZE` | `800` | 分块大小 |
| `RAG_CHUNK_OVERLAP` | `100` | 重叠 |
| `RAG_RETRIEVAL_TOP_K` | `4` | Top-K |
| `RAG_AGENTS` | `literature,theory,general` | 启用 RAG 的 Agent（演示可加 `experiment`） |
| `RAG_INDEX_MCP_FILES` | `false` | 启动时索引 MCP 目录 md/txt |

## L4 结构化记忆

| 变量 | 代码默认 | 说明 |
|------|----------|------|
| `STRUCTURED_MEMORY_AGENTS` | `theory,experiment,review` | 注入 L4 的 Agent |

## Docker 容器内路径

Compose 会覆盖为 `/repo/...`（详见 [`docker.md`](docker.md)）：

- `SESSION_DB_PATH=/repo/data/sessions.db`
- `MCP_ALLOWED_DIRS=/repo/data/mcp_files:/repo/data/theory:/repo/data/experiments`
- `THEORY_WORKSPACE_PATH=/repo/data/theory`
- `EXPERIMENTS_PATH=/repo/data/experiments`
- `RAG_CHROMA_PATH=/repo/data/chroma`
- `MCP_CONFIG_PATH=/repo/conf/mcp_servers.json`

镜像内不含 `.env`，须通过 `env_file` 或 `-e` 注入。

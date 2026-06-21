# Task 06 — L3 向量记忆（RAG）

验证 Chroma 本地向量库、文档 ingestion API，以及注入 literature/theory Agent 的 RAG 检索。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

确保 `.env` 含有效 `DEEPSEEK_API_KEY`，用于在线对话冒烟。

## 自动化测试

```bash
pytest tests/ -q
pytest tests/test_rag.py -q
```

预期：**78 passed**（默认 `ORCHESTRATION_BACKEND=legacy`）。

langgraph backend 下，`tests/test_api.py` 仅 mock `GeneralAgent` — 请显式运行多 Agent + RAG 测试：

```bash
ORCHESTRATION_BACKEND=langgraph pytest tests/test_multi_agent.py tests/test_rag.py -q
```

## 功能开关

RAG 在以下配置下生效：

```bash
ENABLE_RAG=true
RAG_CHROMA_PATH=./data/chroma
RAG_EMBEDDING_PROVIDER=chroma_default   # 或 openai、sentence_transformers、test
RAG_AGENTS=literature,theory
```

Literature/theory SubAgent 在调用 LLM 前检索本地 chunk。会话通过 `/v1/sessions/{id}/rag-refs` 存储 **doc_id + 片段预览**，而非在 L2 消息中存完整 RAG 文本。

## 架构（Task 6）

| 组件 | 路径 |
|------|------|
| 分块 | `server/memory/rag/chunking.py` |
| Embedding | `server/memory/rag/embeddings.py` |
| Chroma 存储 + 注册表 | `server/memory/rag/store.py` |
| 检索 + prompt 注入 | `server/memory/rag/retrieval.py` |
| 会话文档引用 | `server/memory/rag/session_refs.py` |
| 文档 API | `server/api/documents.py` |
| Agent 集成 | `server/agents/subagent.py` |
| 配置 | `server/config.py`、`.env.example` |
| Schema | `shared/schemas.py` |

## Embedding 提供方

| Provider | 用途 |
|----------|------|
| `chroma_default` | 本地默认（内置 ONNX 小模型） |
| `sentence_transformers` | 可选：`pip install 'ai4s-research-agent[rag]'` |
| `openai` | OpenAI 兼容 API（`RAG_EMBEDDING_BASE_URL` 或 `DEEPSEEK_BASE_URL`） |
| `test` | pytest 用确定性向量 |

## API 示例

```bash
# 上传 / 索引 markdown
curl -s -X POST http://127.0.0.1:8000/v1/documents \
  -H 'Content-Type: application/json' \
  -d '{"content":"# Adam\nAdam uses adaptive learning rates.","title":"Adam Notes","doc_id":"adam-notes"}'

# 列出已索引文档
curl -s http://127.0.0.1:8000/v1/documents

# 删除文档
curl -s -X DELETE http://127.0.0.1:8000/v1/documents/adam-notes

# 会话 RAG 引用（literature agent 对话后）
curl -s http://127.0.0.1:8000/v1/sessions/{session_id}/rag-refs
```

## 手动对话冒烟（需 API Key）

```bash
ENABLE_RAG=true ORCHESTRATION_BACKEND=langgraph uvicorn server.main:app --port 8000

curl -s -X POST http://127.0.0.1:8000/v1/documents \
  -H 'Content-Type: application/json' \
  -d '{"content":"The local doc mentions phrase RAG-SMOKE-OK for verification.","title":"Smoke","doc_id":"smoke"}'

curl -s -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What phrase is in the local smoke document?","agent":"literature","auto_route":false}'
```

预期回答引用 `RAG-SMOKE-OK`，且 rag-refs 列出 `smoke` doc_id。

## 可选：启动时索引 MCP 文件

```bash
ENABLE_RAG=true RAG_INDEX_MCP_FILES=true
```

索引 `MCP_ALLOWED_DIRS` 下的 `.md` / `.txt` 文件。

## 尚未纳入范围（Task 7/8）

- Docker / docker-compose
- Web RAG 管理 UI

## Task 7（Docker）阻塞项 / 说明

- Chroma 数据位于 `RAG_CHROMA_PATH` — 与 `data/sessions.db`、`data/mcp_files` 一并挂载为卷
- 默认 `chroma_default` embedding 在容器内无需额外 pip extras；`sentence_transformers` 需 `[rag]` extra + 模型缓存卷
- 日志中 Chroma telemetry 警告无害（chromadb 0.5.x）
- compose 中可选独立 Chroma 服务；当前设计使用内嵌 PersistentClient（单容器友好）

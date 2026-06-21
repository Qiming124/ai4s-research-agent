---
name: Task 06 — L3 向量记忆（RAG）
task_id: p5-rag
status: completed
---

# Task 06：L3 向量记忆 — ingestion API + literature/theory 集成

## 目标

Chroma 本地向量库、文档 ingestion API、检索注入 literature/theory 子 Agent；会话存 doc 引用而非完整 RAG 文本。

## 前置条件

- [x] Task 5：`dev` 上多 Agent orchestrator + SubAgent
- [x] LangGraph ReAct 路径 + 按 Agent 工具白名单
- [x] 仅在 `dev` 分支工作，不 push 远程

## 步骤

### Step 1 — 依赖 + 配置

1. `pyproject.toml`：`chromadb`、`sentence-transformers`（embedding 回退）
2. `server/config.py`：`enable_rag`、`rag_chroma_path`、embedding provider/model、chunk size、top_k、rag agents
3. `.env.example` RAG 章节

### Step 2 — `server/memory/rag/`

1. `chunking.py` — 按大小与 overlap 切分 markdown/text
2. `embeddings.py` — OpenAI 兼容或 sentence-transformers；pytest 用 `test` provider
3. `store.py` — Chroma PersistentClient + SQLite 文档注册表
4. `retrieval.py` — query → 排序片段
5. `session_refs.py` — 每会话 doc_id 引用（sessions.db 中 SQLite 表）

### Step 3 — 文档 API

1. `server/api/documents.py` — POST/GET/DELETE `/v1/documents`
2. `shared/schemas.py` 中 schema
3. 在 `server/main.py` 挂载 router

### Step 4 — Agent 集成

1. `server/agents/subagent.py` — `enable_rag` 时为 `literature` + `theory` 检索
2. 调用 LLM 前将片段注入 system 上下文
3. 经 `session_refs` 持久化 doc 引用，不写入 L2 消息正文

### Step 5 — 测试 + benchmark

1. `tests/test_rag.py` — 分块、ingestion、检索、API、subagent 注入（mock）
2. `pytest tests/ -q` + curl 冒烟
3. `benchmarks/task-06-rag.md`
4. 在 `dev` 上逻辑提交
5. 主计划标记 `p5-rag` completed

## 不在范围内（Task 7/8）

- Docker / docker-compose
- Web RAG 管理 UI

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 计划文件 | done | 本文件 |
| RAG 模块 | done | chunking、embeddings、store、retrieval、session_refs |
| API | done | documents.py、schemas |
| Agent 集成 | done | subagent.py literature/theory |
| 测试 + benchmark | done | 78 passed，benchmarks/task-06-rag.md |

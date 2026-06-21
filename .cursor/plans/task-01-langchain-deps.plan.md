---
name: Task 01 — LangChain 依赖与适配层
task_id: p3-langchain-deps
status: completed
---

# Task 01：LangChain 依赖与适配层

## 目标

引入 langchain 栈依赖与 `server/langchain/` 适配层，提供 `get_chat_model()` 工厂（通过 ChatOpenAI 接入 DeepSeek）。新增 `ORCHESTRATION_BACKEND=legacy` 配置开关。暂不迁移 MCP 或 tool loop。

## 前置条件

- [x] 在 `dev` 分支工作
- [ ] Task 1 变更前，将未暂存的 Phase 2B 工作作为基线提交

## 步骤

### Step 1 — 基线提交（Phase 2B）

1. 暂存全部 Phase 2B 文件（MCP、Web 工具 UI、测试、文档），排除 `.cursor/`
2. 提交：`Phase 2B complete: MCP tool layer, session persistence, web tool UI`

### Step 2 — 依赖

1. 在 `pyproject.toml` 增加：
   - `langchain>=0.3.0,<0.4`
   - `langchain-core>=0.3.0,<0.4`
   - `langchain-openai>=0.3.0,<0.4`
   - `langgraph>=0.2.0,<0.3`
   - `langchain-mcp-adapters>=0.1.0`
   - `langgraph-checkpoint-sqlite>=2.0.0,<3`
2. 运行 `pip install -e ".[dev]"` 并解决版本冲突

### Step 3 — 配置

1. 在 `server/config.py` 增加 `orchestration_backend: str = "legacy"`
2. 增加校验器：允许值 `legacy` | `langgraph`
3. 在 `.env.example` 中记录为 `ORCHESTRATION_BACKEND=legacy`

### Step 4 — 适配模块

创建 `server/langchain/`：

| 文件 | 用途 |
|------|------|
| `__init__.py` | 导出 `get_chat_model` |
| `llm.py` | `get_chat_model()` → `ChatOpenAI`，含 DeepSeek base_url、model、max_tokens，reasoning 经 extra_body |

Parity 辅助（可选）：`build_model_kwargs(settings)` 共享逻辑，镜像 `DeepSeekClient._build_create_kwargs`。

### Step 5 — 测试

1. `tests/test_langchain_llm.py`：
   - 使用 mock settings 创建模型
   - 断言 base_url、model、max_tokens、extra_body 含 reasoning/thinking
   - 可选：mock LLM 或经 env 使用真实 key 做 invoke 测试
2. 全量：`pytest tests/ -q`

### Step 6 — 验证与文档

1. 测试通过后 → 编写 `benchmarks/task-01-langchain-deps.md`，含 CLI 验证步骤
2. 逻辑提交：deps、adapter、tests、benchmark doc
3. 更新主计划 frontmatter：`p3-langchain-deps` → completed

## 不在范围内（Task 2–8）

- MCP 迁移至 MultiServerMCPClient
- LangGraph ReAct tool loop
- 移除 `server/llm/client.py`
- 将生产路径切换为 langgraph backend

## 验证命令

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_langchain_llm.py -q
pytest tests/ -q
```

## 状态日志

| 步骤 | 状态 | 备注 |
|------|------|------|
| 基线提交 | done | bf53a5b |
| 依赖 | done | langchain 0.3.x 栈 |
| 配置 | done | ORCHESTRATION_BACKEND=legacy |
| 适配层 | done | server/langchain/llm.py |
| 测试 | done | 43 passed |
| Benchmark 文档 | done | benchmarks/task-01-langchain-deps.md |

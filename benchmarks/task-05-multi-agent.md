# Task 05 — 多 Agent Supervisor 路由

验证 supervisor 路由至 theory/experiment/literature 子 Agent、API/CLI 扩展，以及 `ORCHESTRATION_BACKEND=langgraph` 下的 SSE handoff 事件。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

确保 `.env` 中包含有效的 `DEEPSEEK_API_KEY`。

## 自动化测试

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true pytest tests/ -q
ORCHESTRATION_BACKEND=legacy pytest tests/ -q
pytest tests/test_multi_agent.py -q
```

预期：**65 passed**（langgraph + legacy）。

## 功能开关

多 Agent 路由仅在以下配置下生效：

```bash
ORCHESTRATION_BACKEND=langgraph
```

当 `ORCHESTRATION_BACKEND=legacy` 时，API/CLI 仍接受 `agent` / `auto_route` 字段，但路由仅使用 `GeneralAgent`（无 supervisor handoff）。

## 架构（Task 5）

| 组件 | 路径 |
|------|------|
| Agent 注册表 + prompts | `server/agents/config.py`、`server/llm/prompts.py` |
| 意图路由 | `server/graph/router.py` |
| SubAgent ReAct 运行器 | `server/agents/subagent.py` |
| Supervisor 编排 | `server/agents/orchestrator.py` |
| 按 Agent 工具白名单 | `mcp_tool_whitelist.json`、`server/mcp/whitelist.py` |
| API 路由 | `server/api/chat.py` |
| CLI 参数 | `client/cli.py`（`--agent`、`--auto-route`） |
| SSE schema | `shared/schemas.py`（`agent_handoff`、`route_reason`、`a2a_task_id`） |

## 各 Agent 工具子集

| Agent | 工具 |
|-------|------|
| `general` | 全部（`*`） |
| `theory` | 无（`__none__`） |
| `experiment` | `filesystem__*` |
| `literature` | `arxiv__*`、`web_search__*` |

## API 示例

```bash
# 自动路由（默认）
curl -s -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"检索 arxiv 上 Adam 优化器论文"}'

# 指定 Agent
curl -s -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"分析实验","agent":"experiment","auto_route":false}'

# mode=math → theory agent
curl -s -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"推导损失","mode":"math"}'
```

SSE 事件包含 `meta`（含 `route_reason`）、`agent_handoff`，以及带 `agent_name` / `a2a_task_id` 的 chunk。

## CLI 示例

```bash
research-agent-cli --agent theory --no-auto-route
research-agent-cli --auto-route
research-agent-cli --mode math
```

## 手动验证（可选，需 API Key + MCP）

```bash
ORCHESTRATION_BACKEND=langgraph ENABLE_MCP=true uvicorn server.main:app --port 8000
research-agent-cli --auto-route
```

对 literature/experiment 类 prompt 应出现 handoff 行，流式 chunk 带 `agent_name`。

## 尚未纳入范围（Task 6）

- RAG / L3 向量记忆
- Web Agent 时间线 UI

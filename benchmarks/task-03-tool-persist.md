# Task 03 — 工具调用持久化、截断与白名单

验证 assistant 消息在 SQLite 中持久化 MCP `tool_calls`，工具结果写入 LLM 上下文前截断，以及可选白名单过滤工具。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

## 自动化测试

```bash
pytest tests/test_tool_persist.py tests/test_session.py -q
pytest tests/ -q
```

预期：全部测试通过（53+）。关键用例：
- `test_session_store_tool_calls` — memory + sqlite 往返
- `test_truncate_tool_result_over_limit` — 超限截断并附摘要提示
- `test_general_agent_persists_tool_calls` — Agent 完成时写入 tool 记录

## 手动验证 — GET session API

启用 MCP 后，完成一次使用工具的对话：

```bash
export ENABLE_MCP=true
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

发送触发工具的对话，再拉取会话：

```bash
curl -s -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"List files in mcp_files","enable_tools":true}' | python -m json.tool

# 使用响应中的 session_id:
curl -s http://127.0.0.1:8000/v1/sessions/<session_id> | python -m json.tool
```

预期：assistant 消息包含 `tool_calls` 数组，字段含 `id`、`name`、`arguments`、`result`、`status`。

## 配置

```bash
grep MCP_TOOL .env.example
```

- `MCP_TOOL_RESULT_MAX_CHARS=8000` — 截断写入 LLM 上下文的工具结果
- `MCP_TOOL_WHITELIST` — 逗号分隔 glob 模式（空 = 全部）
- `MCP_TOOL_WHITELIST_PATH` — 可选 JSON，含 `global` + `agents` 映射

## 尚未纳入范围

- LangGraph ReAct 工具循环（Task 4）
- Web UI 从持久化 `tool_calls` 展示工具时间线（Task 7）

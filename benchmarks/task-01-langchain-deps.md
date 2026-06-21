# Task 01 — LangChain 依赖与适配层

验证 LangChain 栈已安装，且 `get_chat_model()` 能产出与 `DeepSeekClient` 配置对齐的 DeepSeek 兼容响应。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

确保 `.env` 中包含有效的 `DEEPSEEK_API_KEY`。

## 自动化测试

```bash
pytest tests/test_langchain_llm.py -q
pytest tests/ -q
```

预期：全部测试通过（含与 `DeepSeekClient._build_create_kwargs` 的 parity 校验）。

## 手动验证（Python REPL）

```bash
python - <<'PY'
import asyncio
from server.config import get_settings
from server.langchain.llm import build_chat_model_kwargs, get_chat_model

settings = get_settings()
print("ORCHESTRATION_BACKEND:", settings.orchestration_backend)  # legacy
print("kwargs:", build_chat_model_kwargs(settings))

async def main():
    model = get_chat_model()
    resp = await model.ainvoke("Reply with exactly: langchain-ok")
    print("content:", resp.content.strip())

asyncio.run(main())
PY
```

预期输出包含 `ORCHESTRATION_BACKEND: legacy` 与 `content: langchain-ok`。

## 配置开关

`ORCHESTRATION_BACKEND` 默认为 `legacy`。生产对话路径仍使用 `server/llm/client.py`。LangGraph 迁移见 Task 2–4。

```bash
grep ORCHESTRATION_BACKEND .env.example
# ORCHESTRATION_BACKEND=legacy
```

## 尚未纳入范围

- 通过 `langchain-mcp-adapters` 接入 MCP（Task 2）
- LangGraph ReAct 工具循环（Task 4）
- 移除 `DeepSeekClient`

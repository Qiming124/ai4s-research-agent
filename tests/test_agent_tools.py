"""GeneralAgent MCP 工具流式转发测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.agents.base import GeneralAgent
from server.llm.client import ChatWithToolsResult, ToolCallRequest
from shared.schemas import StreamChunk


class FakeMCP:
    is_connected = True

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": "test__tool", "parameters": {}}}]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return f"result:{arguments.get('q', '')}"


class FakeLLM:
    def __init__(self) -> None:
        self._round = 0

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ChatWithToolsResult:
        self._round += 1
        if self._round == 1:
            return ChatWithToolsResult(
                content="",
                tool_calls=[
                    ToolCallRequest(id="call-1", name="test__tool", arguments={"q": "x"}),
                ],
            )
        return ChatWithToolsResult(content="final answer from tools")

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(type="content", content="streamed ")
        yield StreamChunk(type="content", content="answer")
        yield StreamChunk(type="done", content="", usage={"total_tokens": 3})


@pytest.mark.asyncio
async def test_general_agent_forwards_tool_loop_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"enable_mcp": True})

    from server.memory.session import InMemorySessionStore

    store = InMemorySessionStore()
    agent = GeneralAgent(
        settings=settings,
        llm_client=FakeLLM(),  # type: ignore[arg-type]
        session_store=store,
        mcp_client=FakeMCP(),  # type: ignore[arg-type]
    )

    chunks: list[StreamChunk] = []
    async for chunk in agent.run("hello", None, enable_tools=True):
        chunks.append(chunk)

    types = [c.type for c in chunks]
    assert "tool_call_start" in types
    assert "tool_call_result" in types
    assert "content" in types
    assert types.count("done") >= 1

    content = "".join(c.content for c in chunks if c.type == "content")
    assert "final answer from tools" in content or "streamed answer" in content

    get_settings.cache_clear()

"""Task 3: tool_calls persistence, truncation, and whitelist tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from server.agents.base import GeneralAgent
from server.llm.client import ChatWithToolsResult, ToolCallRequest
from server.mcp.truncation import truncate_tool_result
from server.mcp.whitelist import filter_openai_tools, tool_matches_whitelist
from shared.schemas import StreamChunk


def test_truncate_tool_result_under_limit() -> None:
    text = "short result"
    assert truncate_tool_result(text, 100) == text


def test_truncate_tool_result_over_limit() -> None:
    text = "x" * 100
    truncated = truncate_tool_result(text, 20)
    assert len(truncated) > 20
    assert truncated.startswith("x" * 20)
    assert "截断" in truncated
    assert "100 字符" in truncated


def test_tool_matches_whitelist_glob() -> None:
    assert tool_matches_whitelist("filesystem__read_file", ["filesystem__*"])
    assert not tool_matches_whitelist("arxiv__search_papers", ["filesystem__*"])
    assert tool_matches_whitelist("anything", ["*"])


def test_filter_openai_tools_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("MCP_TOOL_WHITELIST", "filesystem__*")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    tools = [
        {"type": "function", "function": {"name": "filesystem__read_file"}},
        {"type": "function", "function": {"name": "arxiv__search_papers"}},
    ]
    filtered = filter_openai_tools(tools, settings, agent_name="general")
    names = {t["function"]["name"] for t in filtered}
    assert names == {"filesystem__read_file"}

    get_settings.cache_clear()


def test_filter_openai_tools_json_agent_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    whitelist_file = tmp_path / "whitelist.json"
    whitelist_file.write_text(
        '{"global": [], "agents": {"literature": ["arxiv__*"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_TOOL_WHITELIST_PATH", str(whitelist_file))
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    tools = [
        {"type": "function", "function": {"name": "arxiv__search_papers"}},
        {"type": "function", "function": {"name": "web_search__search"}},
    ]
    filtered = filter_openai_tools(tools, settings, agent_name="literature")
    names = {t["function"]["name"] for t in filtered}
    assert names == {"arxiv__search_papers"}

    get_settings.cache_clear()


class FakeMCP:
    is_connected = True

    def get_openai_tools(self, agent_name: str | None = None) -> list[dict[str, Any]]:
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
        yield StreamChunk(type="content", content="streamed answer")
        yield StreamChunk(type="done", content="", usage={"total_tokens": 3})


class FakeLLMLongToolResult:
    def __init__(self) -> None:
        self._round = 0
        self.tool_content: str = ""

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
                    ToolCallRequest(id="call-1", name="test__tool", arguments={"q": "big"}),
                ],
            )
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if tool_msgs:
            self.tool_content = tool_msgs[-1]["content"]
        return ChatWithToolsResult(content="done after truncate")

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(type="content", content="ok")
        yield StreamChunk(type="done", content="")


@pytest.mark.asyncio
async def test_general_agent_persists_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "legacy")
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

    async for _ in agent.run("hello", None, enable_tools=True):
        pass

    messages = store.get_messages(store.list_session_ids()[0])
    assistant = next(m for m in messages if m.role == "assistant")
    assert assistant.tool_calls is not None
    assert len(assistant.tool_calls) == 1
    assert assistant.tool_calls[0].id == "call-1"
    assert assistant.tool_calls[0].name == "test__tool"
    assert assistant.tool_calls[0].result == "result:x"
    assert assistant.tool_calls[0].status == "success"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_general_agent_truncates_tool_result_for_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "legacy")
    from server.config import get_settings

    get_settings.cache_clear()
    long_result = "y" * 200
    settings = get_settings().model_copy(
        update={"enable_mcp": True, "mcp_tool_result_max_chars": 50}
    )

    from server.memory.session import InMemorySessionStore

    store = InMemorySessionStore()
    fake_mcp = FakeMCP()

    async def long_call(name: str, arguments: dict[str, Any]) -> str:
        return long_result

    fake_mcp.call_tool = long_call  # type: ignore[method-assign]

    fake_llm = FakeLLMLongToolResult()
    agent = GeneralAgent(
        settings=settings,
        llm_client=fake_llm,  # type: ignore[arg-type]
        session_store=store,
        mcp_client=fake_mcp,  # type: ignore[arg-type]
    )

    async for _ in agent.run("hello", None, enable_tools=True):
        pass

    assert len(fake_llm.tool_content) < len(long_result)
    assert "截断" in fake_llm.tool_content

    messages = store.get_messages(store.list_session_ids()[0])
    assistant = next(m for m in messages if m.role == "assistant")
    assert assistant.tool_calls is not None
    assert assistant.tool_calls[0].result == long_result

    get_settings.cache_clear()

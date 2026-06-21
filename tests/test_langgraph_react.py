"""Task 4: LangGraph ReAct path tests with mocked LLM/tools."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool

from server.agents.base import GeneralAgent
from server.graph.react import build_react_graph, messages_from_api_dicts
from server.graph.streaming import stream_react_graph
from shared.schemas import StreamChunk


class ScriptedChatModel(BaseChatModel):
    """按脚本返回 AIMessage，支持 astream 分块输出。"""

    responses: list[Any]
    call_index: int = 0

    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self) -> str:
        return "scripted-test-model"

    def _next_script(self) -> AIMessage | list[AIMessageChunk]:
        idx = min(self.call_index, len(self.responses) - 1)
        self.call_index += 1
        return self.responses[idx]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        item = self._next_script()
        if isinstance(item, list):
            msg = AIMessage(content="".join(c.content for c in item if c.content))
        else:
            msg = item
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, **kwargs)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        item = self._next_script()
        chunks = item if isinstance(item, list) else [AIMessageChunk(content=item.content)]
        for chunk in chunks:
            yield ChatGenerationChunk(message=chunk)

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> Runnable:
        return self


class FakeMCP:
    is_connected = True

    class _Registry:
        def list_tools(self) -> list[Any]:
            from dataclasses import dataclass

            @dataclass
            class Reg:
                qualified_name: str = "test__tool"
                description: str = "test tool"
                input_schema: dict[str, Any] = None

            reg = Reg()
            reg.input_schema = {"type": "object", "properties": {"q": {"type": "string"}}}
            return [reg]

    registry = _Registry()

    def get_openai_tools(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "test__tool",
                    "description": "test",
                    "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                },
            }
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return f"result:{arguments.get('q', '')}"


@pytest.mark.asyncio
async def test_react_graph_tool_loop_streaming() -> None:
    async def _tool_fn(q: str = "") -> str:
        return f"result:{q}"

    tool = StructuredTool.from_function(
        coroutine=_tool_fn,
        name="test__tool",
        description="test",
    )
    tool_model = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"id": "call-1", "name": "test__tool", "args": {"q": "x"}}],
            ),
            AIMessage(content=""),
        ]
    )
    final_model = ScriptedChatModel(
        responses=[
            [
                AIMessageChunk(content="streamed "),
                AIMessageChunk(content="answer"),
            ]
        ]
    )
    graph = build_react_graph(
        tool_model,
        [tool],
        max_tool_rounds=10,
        max_result_chars=8000,
    )
    inputs = {
        "messages": messages_from_api_dicts(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hello"},
            ]
        ),
        "tool_call_records": [],
        "tool_rounds": 0,
    }

    chunks: list[StreamChunk] = []
    records_total: list = []
    async for chunk, records in stream_react_graph(
        graph,
        inputs,
        final_model=final_model,
        agent_name="general",
        max_tool_rounds=10,
    ):
        chunks.append(chunk)
        if records:
            records_total.extend(records)

    types = [c.type for c in chunks]
    assert "tool_call_start" in types
    assert "tool_call_result" in types
    assert "content" in types
    assert types.count("done") >= 1
    assert len(records_total) == 1
    assert records_total[0].result == "result:x"


@pytest.mark.asyncio
async def test_general_agent_langgraph_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "langgraph")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"enable_mcp": True})

    tool_model = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"id": "call-1", "name": "test__tool", "args": {"q": "x"}}],
            ),
            AIMessage(content=""),
        ]
    )
    final_model = ScriptedChatModel(
        responses=[[AIMessageChunk(content="langgraph final answer")]]
    )

    def fake_get_chat_model(*args: Any, **kwargs: Any) -> ScriptedChatModel:
        if kwargs.get("enable_thinking") is False:
            return tool_model
        return final_model

    monkeypatch.setattr("server.agents.base.get_chat_model", fake_get_chat_model)

    from server.memory.session import InMemorySessionStore

    store = InMemorySessionStore()
    agent = GeneralAgent(
        settings=settings,
        llm_client=object(),  # type: ignore[arg-type]
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

    messages = store.get_messages(store.list_session_ids()[0])
    assistant = next(m for m in messages if m.role == "assistant")
    assert assistant.tool_calls is not None
    assert assistant.tool_calls[0].id == "call-1"
    assert assistant.tool_calls[0].result == "result:x"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_general_agent_legacy_path_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "legacy")
    from server.config import get_settings
    from server.llm.client import ChatWithToolsResult, ToolCallRequest

    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"enable_mcp": True})

    class FakeLLM:
        def __init__(self) -> None:
            self._round = 0

        async def chat_with_tools(self, messages, tools, **kwargs):
            self._round += 1
            if self._round == 1:
                return ChatWithToolsResult(
                    content="",
                    tool_calls=[
                        ToolCallRequest(id="call-1", name="test__tool", arguments={"q": "x"}),
                    ],
                )
            return ChatWithToolsResult(content="legacy answer")

        async def stream_chat(self, messages):
            yield StreamChunk(type="content", content="legacy answer")
            yield StreamChunk(type="done", content="")

    from server.memory.session import InMemorySessionStore

    store = InMemorySessionStore()
    agent = GeneralAgent(
        settings=settings,
        llm_client=FakeLLM(),  # type: ignore[arg-type]
        session_store=store,
        mcp_client=FakeMCP(),  # type: ignore[arg-type]
    )

    chunks = []
    async for chunk in agent.run("hello", None, enable_tools=True):
        chunks.append(chunk)

    assert any(c.type == "tool_call_start" for c in chunks)
    assert any(c.type == "content" for c in chunks)

    get_settings.cache_clear()

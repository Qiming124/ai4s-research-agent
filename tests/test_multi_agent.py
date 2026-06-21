"""Task 5: Multi-agent supervisor routing tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.agents.config import AGENT_NAMES
from server.agents.orchestrator import MultiAgentOrchestrator
from server.agents.subagent import SubAgent
from server.graph.router import classify_intent
from shared.schemas import StreamChunk


def test_classify_intent_theory() -> None:
    agent, reason = classify_intent("请证明损失函数的收敛性")
    assert agent == "theory"
    assert "theory" in reason


def test_classify_intent_experiment() -> None:
    agent, reason = classify_intent("分析实验日志中的训练曲线指标")
    assert agent == "experiment"
    assert "experiment" in reason


def test_classify_intent_literature() -> None:
    agent, reason = classify_intent("检索 arxiv 上关于 Adam 优化器的论文")
    assert agent == "literature"
    assert "literature" in reason


def test_classify_intent_math_mode() -> None:
    agent, reason = classify_intent("任意问题", mode="math")
    assert agent == "theory"
    assert reason == "mode=math"


class FakeMCP:
    is_connected = True

    def get_openai_tools(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        all_tools = {
            "filesystem__read_file": {
                "type": "function",
                "function": {"name": "filesystem__read_file", "parameters": {}},
            },
            "arxiv__search_papers": {
                "type": "function",
                "function": {"name": "arxiv__search_papers", "parameters": {}},
            },
            "web_search__search": {
                "type": "function",
                "function": {"name": "web_search__search", "parameters": {}},
            },
        }
        from server.mcp.whitelist import filter_openai_tools
        from server.config import get_settings

        tools = list(all_tools.values())
        return filter_openai_tools(tools, get_settings(), agent_name=agent_name)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return f"result:{name}"


class ScriptedSubAgent(SubAgent):
    """SubAgent that yields scripted chunks without LLM."""

    async def run(
        self,
        message: str,
        session_id: str | None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        a2a = kwargs.get("a2a_task_id")
        yield StreamChunk(
            type="content",
            content=f"[{self.name}] handled: {message[:20]}",
            agent_name=self.name,
            a2a_task_id=a2a,
        )
        yield StreamChunk(
            type="done",
            content="",
            usage={"session_id": session_id or "test-session", "total_tokens": 1},
            agent_name=self.name,
            a2a_task_id=a2a,
        )


@pytest.mark.asyncio
async def test_orchestrator_routes_three_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "langgraph")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    orchestrator = MultiAgentOrchestrator(settings=settings, mcp_client=FakeMCP())  # type: ignore[arg-type]

    prompts = [
        ("证明梯度下降的收敛定理", "theory"),
        ("读取实验日志分析训练指标", "experiment"),
        ("检索相关论文综述", "literature"),
    ]

    for message, expected in prompts:
        target, _ = orchestrator.resolve_target_agent(message, auto_route=True)
        assert target == expected, f"message={message}"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_orchestrator_handoff_sse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "langgraph")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    orchestrator = MultiAgentOrchestrator(settings=settings, mcp_client=FakeMCP())  # type: ignore[arg-type]

    agents: dict[str, ScriptedSubAgent] = {}
    for name in AGENT_NAMES:
        agents[name] = ScriptedSubAgent(name, settings=settings, mcp_client=FakeMCP())  # type: ignore[arg-type]

    def fake_get_agent(name: str) -> ScriptedSubAgent:
        return agents[name]

    orchestrator._get_agent = fake_get_agent  # type: ignore[method-assign]

    chunks: list[StreamChunk] = []
    async for chunk in orchestrator.run(
        "检索 arxiv 论文",
        "sess-1",
        auto_route=True,
    ):
        chunks.append(chunk)

    handoffs = [c for c in chunks if c.type == "agent_handoff"]
    assert len(handoffs) == 1
    assert handoffs[0].from_agent == "supervisor"
    assert handoffs[0].to_agent == "literature"
    assert handoffs[0].a2a_task_id is not None

    content_chunks = [c for c in chunks if c.type == "content"]
    assert content_chunks[0].agent_name == "literature"
    assert content_chunks[0].a2a_task_id == handoffs[0].a2a_task_id

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_explicit_agent_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "langgraph")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    orchestrator = MultiAgentOrchestrator(settings=settings, mcp_client=FakeMCP())  # type: ignore[arg-type]
    target, reason = orchestrator.resolve_target_agent(
        "检索论文",
        agent="experiment",
        auto_route=True,
    )
    assert target == "experiment"
    assert reason == "explicit:experiment"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_subagent_whitelist_filters_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"enable_mcp": True})
    mcp = FakeMCP()

    lit_tools = mcp.get_openai_tools(agent_name="literature")
    lit_names = {t["function"]["name"] for t in lit_tools}
    assert "arxiv__search_papers" in lit_names
    assert "filesystem__read_file" not in lit_names

    exp_tools = mcp.get_openai_tools(agent_name="experiment")
    exp_names = {t["function"]["name"] for t in exp_tools}
    assert "filesystem__read_file" in exp_names
    assert "arxiv__search_papers" not in exp_names

    theory_tools = mcp.get_openai_tools(agent_name="theory")
    assert theory_tools == []

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_legacy_general_agent_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.setenv("ORCHESTRATION_BACKEND", "legacy")
    from server.agents.base import GeneralAgent
    from server.config import get_settings

    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"enable_mcp": False})

    class FakeLLM:
        async def stream_chat(self, messages):
            yield StreamChunk(type="content", content="legacy ok")
            yield StreamChunk(type="done", content="")

    from server.memory.session import InMemorySessionStore

    store = InMemorySessionStore()
    agent = GeneralAgent(
        settings=settings,
        llm_client=FakeLLM(),  # type: ignore[arg-type]
        session_store=store,
    )

    chunks = []
    async for chunk in agent.run("hello", None):
        chunks.append(chunk)

    assert any(c.type == "content" for c in chunks)
    assert agent.name == "general"

    get_settings.cache_clear()

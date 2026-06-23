# 多 Agent 编排：意图路由 + 子 Agent 委派 + handoff SSE。

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from server.agents.config import AgentName, normalize_agent_name
from server.agents.subagent import SubAgent
from server.config import Settings, get_settings
from server.graph.router import classify_intent
from server.mcp.client import MCPClient
from shared.schemas import StreamChunk

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """Supervisor：classify_intent → route → SubAgent ReAct 子图。"""

    def __init__(
        self,
        settings: Settings | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._mcp = mcp_client
        self._agents: dict[AgentName, SubAgent] = {}

    def _get_agent(self, name: AgentName) -> SubAgent:
        if name not in self._agents:
            self._agents[name] = SubAgent(
                name,
                settings=self._settings,
                mcp_client=self._mcp,
            )
        return self._agents[name]

    def resolve_target_agent(
        self,
        message: str,
        *,
        agent: str | None = None,
        auto_route: bool = True,
        mode: str = "chat",
    ) -> tuple[AgentName, str]:
        explicit = normalize_agent_name(agent)
        if explicit is not None:
            return explicit, f"explicit:{explicit}"

        if auto_route:
            return classify_intent(message, mode=mode)

        return "general", "auto_route_disabled"

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        agent: str | None = None,
        auto_route: bool = True,
        mode: str = "chat",
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
    ) -> AsyncIterator[StreamChunk]:
        target, route_reason = self.resolve_target_agent(
            message,
            agent=agent,
            auto_route=auto_route,
            mode=mode,
        )
        a2a_task_id = str(uuid.uuid4())
        from_agent = "supervisor"

        logger.info(
            "Orchestrator route: %s → %s (%s) task=%s",
            from_agent,
            target,
            route_reason,
            a2a_task_id,
        )

        yield StreamChunk(
            type="agent_handoff",
            content=route_reason,
            from_agent=from_agent,
            to_agent=target,
            route_reason=route_reason,
            agent_name=target,
            a2a_task_id=a2a_task_id,
        )

        sub_agent = self._get_agent(target)
        async for chunk in sub_agent.run(
            message,
            session_id,
            system_prompt_override=system_prompt_override,
            max_history_messages=max_history_messages,
            enable_history_summary=enable_history_summary,
            enable_tools=enable_tools,
            a2a_task_id=a2a_task_id,
        ):
            yield chunk

    async def run_sync(
        self,
        message: str,
        session_id: str | None,
        *,
        agent: str | None = None,
        auto_route: bool = True,
        mode: str = "chat",
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
    ) -> tuple[str, str, str, dict | None, AgentName, str]:
        sid = session_id or ""
        content = ""
        reasoning = ""
        usage: dict | None = None
        target: AgentName = "general"
        route_reason = ""

        async for chunk in self.run(
            message,
            session_id,
            agent=agent,
            auto_route=auto_route,
            mode=mode,
            system_prompt_override=system_prompt_override,
            max_history_messages=max_history_messages,
            enable_history_summary=enable_history_summary,
            enable_tools=enable_tools,
        ):
            if chunk.type == "agent_handoff":
                target = normalize_agent_name(chunk.to_agent) or target
                route_reason = chunk.route_reason or chunk.content
            elif chunk.type == "reasoning":
                reasoning += chunk.content
            elif chunk.type == "content":
                content += chunk.content
            elif chunk.type == "done":
                usage = chunk.usage
                if usage and "session_id" in usage:
                    sid = str(usage["session_id"])

        return sid, content, reasoning or "", usage, target, route_reason


_orchestrator: MultiAgentOrchestrator | None = None


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentOrchestrator()
    return _orchestrator


def reset_multi_agent_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None

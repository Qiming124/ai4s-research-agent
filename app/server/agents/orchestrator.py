# =============================================================================
# 多 Agent 编排器（Supervisor）。
#
# 职责：
#     1. 解析用户意图并路由到 theory / experiment / literature 等子 Agent
#     2. 检测 /research 关键词并委派 ResearchSupervisorPipeline（8 阶段 Campaign）
#     3. 发出 agent_handoff SSE 事件，再流式转发 SubAgent 输出
#     4. 提供 run / run_sync 两种入口（流式与非流式聚合）
#
# 架构位置：
#     - 被调用：server/api/chat.py → get_multi_agent_orchestrator().run(...)
#     - 调用：server/agents/subagent.py、server/graph/research_supervisor.py、
#             server/graph/router_llm.py、server/graph/research_pipeline.py
#
# 阅读提示：
#     - 新人先看 resolve_target_agent() 与 run() 的分支逻辑
#     - 再看 _get_agent() 如何按 AgentName 实例化 SubAgent
#
# Debug：
#     - 路由总走 general → 检查 ROUTER_USE_LLM 与 classify_intent_smart 日志
#     - 未进入 Campaign → should_use_research_pipeline 条件或 RESEARCH_PIPELINE_MODE
#     - handoff 后无输出 → 检查 SubAgent.run 与 MCP 连接状态
# =============================================================================

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from server.agents.config import AgentName, normalize_agent_name
from server.agents.subagent import SubAgent
from server.config import Settings, get_settings
from server.graph.research_pipeline import should_use_research_pipeline
from server.graph.research_supervisor import ResearchSupervisorPipeline
from server.graph.router_llm import classify_intent_smart
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

    async def resolve_target_agent(
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
            return await classify_intent_smart(message, mode=mode, settings=self._settings)

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
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        cot_mode: str = "standard",
        project_id: str | None = None,
        campaign_id: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        流式执行多 Agent 对话：路由 → handoff SSE → SubAgent 或 Campaign 流水线。

        参数:
            message: 用户输入
            session_id: 会话 ID（可选）
            agent: 强制指定 Agent 名称时跳过自动路由
            auto_route: 是否启用意图分类
            mode: chat / research 等模式
            project_id / campaign_id: Campaign 流水线上下文

        返回:
            StreamChunk 异步迭代器（SSE 事件源）
        """
        if (
            agent is None
            and auto_route
            and should_use_research_pipeline(message, mode, self._settings)
        ):
            pipeline = ResearchSupervisorPipeline(
                settings=self._settings,
                mcp_client=self._mcp,
            )
            async for chunk in pipeline.execute(
                message,
                session_id,
                mode=mode,
                project_id=project_id,
                campaign_id=campaign_id,
                system_prompt_override=system_prompt_override,
                max_history_messages=max_history_messages,
                enable_history_summary=enable_history_summary,
                enable_tools=enable_tools,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
                cot_mode=cot_mode,
            ):
                yield chunk
            return

        target, route_reason = await self.resolve_target_agent(
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
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,
            cot_mode=cot_mode,
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
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        cot_mode: str = "standard",
        project_id: str | None = None,
        campaign_id: str | None = None,
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
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,
            cot_mode=cot_mode,
            project_id=project_id,
            campaign_id=campaign_id,
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

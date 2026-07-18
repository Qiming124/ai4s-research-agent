# 研究流水线：literature → theory → experiment → review 多跳编排。

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from server.agents.config import AgentName
from server.agents.subagent import SubAgent
from server.config import Settings, get_settings
from server.graph.theory_pipeline import needs_experiment_handoff
from server.mcp.client import MCPClient
from shared.schemas import StreamChunk

logger = logging.getLogger(__name__)

_RESEARCH_KEYWORDS = (
    "证明", "推导", "定理", "引理", "局部极小", "鞍点", "loss landscape",
    "hessian", "验证", "综述", "文献",
)


def should_use_research_pipeline(message: str, mode: str, settings: Settings) -> bool:
    if settings.research_pipeline_mode != "auto":
        return False
    if message.strip().startswith("/research"):
        return True
    if mode == "math":
        return True
    lower = message.lower()
    hits = sum(1 for kw in _RESEARCH_KEYWORDS if kw in lower or kw in message)
    return hits >= 2


class ResearchPipeline:
    """多跳研究流水线执行器。"""

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

    async def _stage(
        self,
        stage: str,
        agent_name: AgentName,
        message: str,
        session_id: str | None,
        a2a_task_id: str,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(
            type="pipeline_stage",
            content=stage,
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
            title=stage,
        )
        yield StreamChunk(
            type="agent_handoff",
            content=f"pipeline:{stage}",
            from_agent="supervisor",
            to_agent=agent_name,
            route_reason=f"pipeline:{stage}",
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
        )
        agent = self._get_agent(agent_name)
        async for chunk in agent.run(
            message,
            session_id,
            a2a_task_id=a2a_task_id,
            **kwargs,
        ):
            yield chunk

    async def execute(
        self,
        message: str,
        session_id: str | None,
        *,
        mode: str = "chat",
        **run_kwargs,
    ) -> AsyncIterator[StreamChunk]:
        a2a_task_id = str(uuid.uuid4())
        clean_message = message.removeprefix("/research").strip() or message

        # Stage 1: Literature background
        lit_prompt = (
            f"请检索与下列问题相关的损失函数/局部极小值/优化理论文献，"
            f"给出简短背景综述（3-5 篇）：\n\n{clean_message}"
        )
        async for chunk in self._stage(
            "literature_background",
            "literature",
            lit_prompt,
            session_id,
            a2a_task_id,
            **run_kwargs,
        ):
            yield chunk

        # Stage 2: Theory derivation
        theory_prompt = (
            f"在以下研究问题基础上进行形式化与推导（引用上文文献背景若相关）：\n\n"
            f"{clean_message}"
        )
        theory_content = ""
        sympy_result: dict = {}
        num_result: dict | None = None
        async for chunk in self._stage(
            "theory_derivation",
            "theory",
            theory_prompt,
            session_id,
            a2a_task_id,
            mode="math",
            **run_kwargs,
        ):
            if chunk.type == "content":
                theory_content += chunk.content
            elif chunk.type == "verification_result":
                try:
                    sympy_result = json.loads(chunk.content)
                except json.JSONDecodeError:
                    pass
            elif chunk.type == "numerical_verification_result":
                try:
                    num_result = json.loads(chunk.content)
                except json.JSONDecodeError:
                    pass
            yield chunk

        # Stage 3: Experiment (conditional)
        if needs_experiment_handoff(sympy_result, num_result):
            from server.experiments.runner import run_config_async

            exp_prompt = (
                f"请对以下理论推导进行数值验证（使用 numerical MCP）：\n\n"
                f"{theory_content[:3000] if theory_content else clean_message}"
            )
            try:
                auto_record = await run_config_async(
                    "quadratic_minimum.yaml",
                    session_id=session_id,
                )
                yield StreamChunk(
                    type="numerical_verification_result",
                    content=json.dumps(auto_record.get("summary", auto_record), ensure_ascii=False),
                    agent_name="experiment",
                    a2a_task_id=a2a_task_id,
                )
                num_result = auto_record.get("summary", auto_record)
            except Exception as exc:
                logger.warning("自动实验执行失败，回退 Experiment Agent: %s", exc)
            async for chunk in self._stage(
                "experiment_verify",
                "experiment",
                exp_prompt,
                session_id,
                a2a_task_id,
                **run_kwargs,
            ):
                if chunk.type == "numerical_verification_result":
                    try:
                        num_result = json.loads(chunk.content)
                    except json.JSONDecodeError:
                        pass
                yield chunk

        # Stage 4: Review
        review_prompt = (
            f"请对照审稿清单审查以下推导，给出审稿意见：\n\n"
            f"{theory_content[:4000] if theory_content else clean_message}"
        )
        async for chunk in self._stage(
            "review",
            "review",
            review_prompt,
            session_id,
            a2a_task_id,
            **run_kwargs,
        ):
            yield chunk

        yield StreamChunk(
            type="pipeline_stage",
            content="complete",
            agent_name="supervisor",
            a2a_task_id=a2a_task_id,
            title="研究流水线完成",
            status="done",
        )

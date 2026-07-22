# =============================================================================
# 场景工作流路由：2–3 跳协作，RESEARCH_PIPELINE_MODE=auto 主路径。
# =============================================================================

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from server.agents.config import AgentName, normalize_agent_name
from server.agents.subagent import SubAgent
from server.artifacts.extract import extract_artifacts_from_text
from server.artifacts.store import get_artifact_store
from server.config import Settings, get_settings
from server.mcp.client import MCPClient
from shared.schemas import StreamChunk

logger = logging.getLogger(__name__)

SceneId = Literal["lit_to_theory", "experiment_plan", "data_to_nextstep"]

_METHOD_HINTS = ("方法", "公式", "推导", "形式化", "证明思路", "method", "/method")
_DATA_HINTS = ("结果", "指标", "日志", "解读", "数据", "metrics", "upload", "下一步")
_REVIEW_HINTS = ("审稿", "审查", "checklist")


@dataclass
class SceneMatch:
    scene_id: SceneId
    reason: str


def match_scene(
    message: str,
    *,
    agent: str | None,
    mode: str,
    settings: Settings,
    project_id: str = "default",
    session_id: str | None = None,
) -> SceneMatch | None:
    """仅在 research_pipeline_mode=auto 时由编排器调用。"""
    if settings.research_pipeline_mode != "auto":
        return None

    text = message.strip()
    lower = text.lower()
    explicit = normalize_agent_name(agent)

    if "/method" in lower or (
        explicit == "literature"
        and any(h in text or h in lower for h in _METHOD_HINTS)
    ):
        return SceneMatch("lit_to_theory", "scene:lit_to_theory")

    if explicit == "experiment":
        store = get_artifact_store()
        has_data = bool(store.latest_datapackets(project_id, session_id=session_id, limit=1))
        wants_data = any(h in text or h in lower for h in _DATA_HINTS)
        if has_data or wants_data:
            return SceneMatch("data_to_nextstep", "scene:data_to_nextstep")
        return SceneMatch("experiment_plan", "scene:experiment_plan")

    return None


_ARTIFACT_HINT = """

请在回答末尾附加 JSON 工件围栏（勿省略），格式：
```artifact:{type}
{{...字段 JSON...}}
```
"""


def _persist_from_content(
    content: str,
    *,
    artifact_hint_type: str,
    project_id: str,
    session_id: str | None,
    agent_name: str,
) -> list[StreamChunk]:
    if not content.strip():
        return []
    store = get_artifact_store()
    settings = get_settings()
    if not settings.enable_artifact_store:
        return []
    chunks: list[StreamChunk] = []
    extracted = extract_artifacts_from_text(content)
    for atype, payload in extracted:
        payload.setdefault("project_id", project_id)
        if session_id:
            payload.setdefault("session_id", session_id)
        try:
            saved = store.save(atype, payload)
        except Exception as exc:
            logger.warning("artifact 落盘失败 type=%s: %s", atype, exc)
            chunks.append(
                StreamChunk(
                    type="error",
                    content=f"工件 {atype} 保存失败（已跳过）：{exc}",
                    agent_name=agent_name,
                )
            )
            continue
        title = saved.get("title") or saved.get("id")
        chunks.append(
            StreamChunk(
                type="artifact_saved",
                content=json.dumps(
                    {"type": atype, "id": saved["id"], "title": title},
                    ensure_ascii=False,
                ),
                agent_name=agent_name,
                title=str(title),
            )
        )
    return chunks


class SceneExecutor:
    def __init__(
        self,
        settings: Settings | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._mcp = mcp_client
        self._agents: dict[AgentName, SubAgent] = {}

    def _agent(self, name: AgentName) -> SubAgent:
        if name not in self._agents:
            self._agents[name] = SubAgent(
                name,
                settings=self._settings,
                mcp_client=self._mcp,
            )
        return self._agents[name]

    async def _run_agent(
        self,
        name: AgentName,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        enable_tools: bool | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        cot_mode: str = "standard",
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        a2a_task_id: str | None = None,
        persist_session: bool = True,
    ) -> AsyncIterator[StreamChunk]:
        agent = self._agent(name)
        async for chunk in agent.run(
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
            persist_session=persist_session,
        ):
            yield chunk

    async def execute(
        self,
        scene: SceneMatch,
        message: str,
        session_id: str | None,
        *,
        project_id: str = "default",
        mode: str = "chat",
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        cot_mode: str = "standard",
    ) -> AsyncIterator[StreamChunk]:
        pid = project_id or "default"
        clean_msg = re.sub(r"^/method\s*", "", message.strip(), flags=re.I)

        if scene.scene_id == "lit_to_theory":
            yield StreamChunk(
                type="pipeline_stage",
                content="文献方法",
                title="文献",
                status="running",
                agent_name="literature",
            )
            lit_prompt = (
                clean_msg
                + "\n\n请用清晰 Markdown 提炼方法要点（问题设定、假设、步骤、公式骨架）；"
                "不要输出 MethodCard 或 artifact 围栏。"
            )
            lit_content = ""
            async for chunk in self._run_agent(
                "literature",
                lit_prompt,
                session_id,
                system_prompt_override=system_prompt_override,
                enable_tools=enable_tools,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
                cot_mode=cot_mode,
                max_history_messages=max_history_messages,
                enable_history_summary=enable_history_summary,
            ):
                if chunk.type == "content":
                    lit_content += chunk.content
                yield chunk

            yield StreamChunk(
                type="pipeline_stage",
                content="理论形式化",
                title="理论",
                status="running",
                agent_name="theory",
            )
            theory_msg = (
                f"请基于以下文献方法提炼，对照课题符号/假设做形式化推导：\n\n{lit_content[:6000]}"
                + _ARTIFACT_HINT.replace("{type}", "DerivationTrace")
                + "\n字段含: steps([{title,body,status}]), title, claim_yaml(可选)"
            )
            theory_content = ""
            async for chunk in self._run_agent(
                "theory",
                theory_msg,
                session_id,
                enable_tools=enable_tools,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
                cot_mode="strict",
                max_history_messages=max_history_messages,
                enable_history_summary=enable_history_summary,
                persist_session=True,
            ):
                if chunk.type == "content":
                    theory_content += chunk.content
                yield chunk
            for c in _persist_from_content(
                theory_content,
                artifact_hint_type="DerivationTrace",
                project_id=pid,
                session_id=session_id,
                agent_name="theory",
            ):
                yield c

            if any(h in clean_msg for h in _REVIEW_HINTS):
                yield StreamChunk(
                    type="pipeline_stage",
                    content="审稿",
                    title="理论",
                    status="running",
                    agent_name="review",
                )
                async for chunk in self._run_agent(
                    "review",
                    f"请审阅以下推导：\n\n{theory_content[:6000]}",
                    session_id,
                    enable_tools=False,
                    enable_thinking=enable_thinking,
                    reasoning_effort=reasoning_effort,
                    cot_mode=cot_mode,
                ):
                    yield chunk
            return

        if scene.scene_id == "experiment_plan":
            yield StreamChunk(
                type="pipeline_stage",
                content="实验计划",
                title="产出",
                status="running",
                agent_name="experiment",
            )
            plan_msg = (
                clean_msg
                + _ARTIFACT_HINT.replace("{type}", "ExperimentPlan")
                + "\n字段含: objectives, variables, controls, hyperparams, success_criteria,"
                " record_fields, notes, title, status(planned|active|done|superseded),"
                " parent_plan_id(可选), revision_note(可选)"
                "\n重要：每次给出新计划或修订计划都必须新写一条 ExperimentPlan 围栏；"
                "不要覆盖历史计划。修订时 status=planned，并在 revision_note / parent_plan_id 注明依据。"
            )
            content = ""
            async for chunk in self._run_agent(
                "experiment",
                plan_msg,
                session_id,
                enable_tools=enable_tools,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
                cot_mode=cot_mode,
                max_history_messages=max_history_messages,
                enable_history_summary=enable_history_summary,
            ):
                if chunk.type == "content":
                    content += chunk.content
                yield chunk
            for c in _persist_from_content(
                content,
                artifact_hint_type="ExperimentPlan",
                project_id=pid,
                session_id=session_id,
                agent_name="experiment",
            ):
                yield c
            return

        # data_to_nextstep
        yield StreamChunk(
            type="pipeline_stage",
            content="数据解读",
            title="产出",
            status="running",
            agent_name="experiment",
        )
        packets = get_artifact_store().latest_datapackets(pid, session_id=session_id, limit=3)
        packet_blob = json.dumps(
            [p.model_dump() for p in packets],
            ensure_ascii=False,
            indent=2,
        )
        next_msg = (
            f"用户问题：{clean_msg}\n\n近期提交数据（DataPacket）：\n{packet_blob}\n\n"
            "请对照理论给出判读与下一步建议。"
            + _ARTIFACT_HINT.replace("{type}", "NextStepMemo")
            + "\n字段含: data_packet_id, verdict, missing_data, next_experiments, notes, title"
            + "\n若 next_experiments 非空，请再输出一份新的 ExperimentPlan（修订计划，追加到历史，不覆盖旧计划）："
            + _ARTIFACT_HINT.replace("{type}", "ExperimentPlan")
            + "\nExperimentPlan 字段含: objectives, variables, controls, success_criteria, record_fields,"
            " title, status=planned, revision_note, parent_plan_id(若知旧计划 id)"
        )
        content = ""
        async for chunk in self._run_agent(
            "experiment",
            next_msg,
            session_id,
            enable_tools=enable_tools,
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,
            cot_mode=cot_mode,
            max_history_messages=max_history_messages,
            enable_history_summary=enable_history_summary,
        ):
            if chunk.type == "content":
                content += chunk.content
            yield chunk
        for c in _persist_from_content(
            content,
            artifact_hint_type="NextStepMemo",
            project_id=pid,
            session_id=session_id,
            agent_name="experiment",
        ):
            yield c
        # 同一次回答里若还带有修订 ExperimentPlan，已由 extract 一并落盘
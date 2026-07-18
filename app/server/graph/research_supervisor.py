# 科研 Supervisor 流水线：8 阶段 Campaign 编排 + 门禁 + 上下文传递。

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from server.agents.config import AgentName
from server.agents.subagent import SubAgent
from server.config import Settings, get_settings
from server.experiments.campaign_experiments import run_campaign_experiments
from server.memory.campaigns import CAMPAIGN_STAGES, campaign_artifacts_dir, get_campaign_store
from server.memory.projects import get_project_store
from server.mcp.client import MCPClient
from shared.paths import DATA_ROOT
from shared.schemas import StreamChunk

from server.graph.research_pipeline import should_use_research_pipeline

logger = logging.getLogger(__name__)

_STAGE_PIPELINE_NAMES: dict[str, str] = {
    "S0_campaign": "campaign_bootstrap",
    "S1_literature": "literature_background",
    "S2_formalization": "problem_formalization",
    "S3_theory": "theory_derivation",
    "S4_counterexample": "counterexample_search",
    "S5_experiment": "experiment_verify",
    "S6_synthesis": "synthesis_report",
    "S7_review": "review",
    "S8_archive": "campaign_archive",
}

_STAGE_TASK_TITLES: dict[str, tuple[str, str]] = {
    "S1_literature": ("文献调研：局部极小值综述", "literature"),
    "S2_formalization": ("形式化：PL 条件推导", "theorist"),
    "S3_theory": ("形式化：PL 条件推导", "theorist"),
    "S5_experiment": ("数值验证：二次损失临界点", "experimenter"),
    "S7_review": ("模拟审稿与修订", "reviewer"),
}


def _stage_index(stage: str) -> int:
    try:
        return CAMPAIGN_STAGES.index(stage)
    except ValueError:
        return 0


def _truncate(text: str, limit: int = 3000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…（截断）"


def _build_context_pack(campaign: dict[str, Any]) -> dict[str, Any]:
    artifacts = campaign.get("stage_artifacts") or {}
    return {
        "campaign_id": campaign.get("id"),
        "title": campaign.get("title"),
        "assumptions": campaign.get("assumptions", []),
        "task_family": campaign.get("task_family"),
        "dataset": campaign.get("dataset"),
        "benchmark": campaign.get("benchmark"),
        "literature_digest": artifacts.get("S1_literature", {}),
        "problem_statement": artifacts.get("S2_formalization", {}),
        "theory_summary": artifacts.get("S3_theory", {}),
        "counterexample_summary": artifacts.get("S4_counterexample", {}),
        "experiment_summary": artifacts.get("S5_experiment", {}),
    }


def _format_context_prompt(context: dict[str, Any]) -> str:
    parts = [
        f"【Campaign】{context.get('title', '')}",
        f"假设：{', '.join(context.get('assumptions') or [])}",
    ]
    lit = context.get("literature_digest") or {}
    if lit.get("summary"):
        parts.append(f"【文献摘要】\n{lit['summary']}")
    prob = context.get("problem_statement") or {}
    if prob.get("summary"):
        parts.append(f"【问题陈述】\n{prob['summary']}")
    theory = context.get("theory_summary") or {}
    if theory.get("summary"):
        parts.append(f"【已有理论】\n{_truncate(theory['summary'], 2000)}")
    return "\n\n".join(parts)


def _check_gate(stage: str, artifact: dict[str, Any], exp_results: dict[str, Any] | None) -> tuple[str, str]:
    """返回 (status, reason)。status: pass|fail|skipped"""
    if stage == "S1_literature":
        count = int(artifact.get("reference_count", 0))
        if count >= 1 or artifact.get("summary"):
            return "pass", "文献阶段已产出综述"
        return "fail", "文献阶段未产出有效综述"

    if stage == "S3_theory":
        vstatus = str(artifact.get("verification_status", ""))
        if vstatus in ("pass", "partial"):
            return "pass", f"理论验证状态: {vstatus}"
        if artifact.get("summary"):
            return "partial_pass", "有理论产出但验证未完全通过"
        return "fail", "理论推导或验证未通过"

    if stage == "S5_experiment":
        if exp_results and exp_results.get("quadratic_pass"):
            return "pass", "二次/符号实验通过"
        if exp_results and exp_results.get("runs"):
            return "partial_pass", "实验已运行但未全部通过"
        return "fail", "实验未成功执行"

    if stage == "S7_review":
        text = artifact.get("summary", "")
        fatal = ("致命", "fatal", "major flaw", "严重缺陷")
        if any(f in text.lower() or f in text for f in fatal):
            return "fail", "审稿发现致命缺陷"
        if text:
            return "pass", "审稿完成"
        return "fail", "审稿未产出意见"

    return "skipped", "无门禁"


def _sync_task_for_stage(project_id: str, stage: str, status: str) -> None:
    mapping = _STAGE_TASK_TITLES.get(stage)
    if not mapping:
        return
    title, _role = mapping
    store = get_project_store()
    tasks = store.list_tasks(project_id)
    for task in tasks:
        if task["title"] == title:
            store.update_task_status(task["id"], status)
            return


class ResearchSupervisorPipeline:
    """8 阶段 Campaign 主管道。"""

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

    def _resolve_campaign(
        self,
        project_id: str,
        campaign_id: str | None,
        session_id: str | None,
        clean_message: str,
    ) -> dict[str, Any]:
        store = get_campaign_store()
        camp = store.get_active_campaign(project_id, campaign_id)
        if camp:
            if session_id and not camp.get("session_id"):
                store.update_campaign(camp["id"], session_id=session_id)
                camp = store.get_campaign(camp["id"]) or camp
            return camp
        return store.create_campaign(
            project_id,
            title=clean_message[:120] or "新科研 Campaign",
            assumptions=["A1", "A4", "A6"],
            session_id=session_id,
        )

    async def _emit_campaign_update(
        self,
        campaign: dict[str, Any],
        a2a_task_id: str,
        *,
        detail: str = "",
    ) -> StreamChunk:
        payload = {
            "campaign_id": campaign["id"],
            "project_id": campaign["project_id"],
            "current_stage": campaign.get("current_stage"),
            "status": campaign.get("status"),
            "gates": campaign.get("gates", {}),
            "detail": detail,
        }
        return StreamChunk(
            type="campaign_update",
            content=json.dumps(payload, ensure_ascii=False),
            agent_name="supervisor",
            a2a_task_id=a2a_task_id,
            title=campaign.get("current_stage"),
            detail=detail or None,
        )

    async def _emit_gate(
        self,
        stage: str,
        status: str,
        reason: str,
        a2a_task_id: str,
    ) -> StreamChunk:
        gate_status = "pass" if status in ("pass", "partial_pass") else "fail"
        return StreamChunk(
            type="pipeline_gate",
            content=json.dumps(
                {"stage": stage, "status": gate_status, "reason": reason},
                ensure_ascii=False,
            ),
            agent_name="supervisor",
            a2a_task_id=a2a_task_id,
            status=gate_status,  # type: ignore[arg-type]
            title=f"门禁 {stage}",
            detail=reason,
        )

    async def _stage(
        self,
        stage: str,
        agent_name: AgentName,
        message: str,
        session_id: str | None,
        a2a_task_id: str,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        pipe_name = _STAGE_PIPELINE_NAMES.get(stage, stage)
        yield StreamChunk(
            type="pipeline_stage",
            content=pipe_name,
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
            title=pipe_name,
        )
        yield StreamChunk(
            type="agent_handoff",
            content=f"pipeline:{pipe_name}",
            from_agent="supervisor",
            to_agent=agent_name,
            route_reason=f"pipeline:{pipe_name}",
            agent_name=agent_name,
            a2a_task_id=a2a_task_id,
        )
        agent = self._get_agent(agent_name)
        # SubAgent.run 不接受 mode；math 路由已由 agent_name=theory 体现
        kwargs.pop("mode", None)
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
        project_id: str | None = None,
        campaign_id: str | None = None,
        **run_kwargs,
    ) -> AsyncIterator[StreamChunk]:
        a2a_task_id = str(uuid.uuid4())
        clean_message = message.removeprefix("/research").strip() or message
        proj_store = get_project_store()
        if session_id:
            resolved_pid = project_id or proj_store.get_project_for_session(session_id)
        else:
            resolved_pid = project_id or "default"
        resolved_pid = proj_store.resolve_project_id(resolved_pid) or "default"

        if session_id:
            proj_store.link_session(resolved_pid, session_id)

        camp_store = get_campaign_store()
        campaign = self._resolve_campaign(
            resolved_pid, campaign_id, session_id, clean_message
        )
        campaign_id = campaign["id"]

        yield await self._emit_campaign_update(
            campaign, a2a_task_id, detail="Campaign 已加载",
        )

        start_idx = _stage_index(str(campaign.get("current_stage", "S0_campaign")))
        if start_idx > 0 and campaign.get("status") == "active":
            logger.info("从阶段 %s 续跑 Campaign %s", campaign.get("current_stage"), campaign_id)

        context = _build_context_pack(campaign)
        context_prefix = _format_context_prompt(context)

        theory_content = ""
        sympy_result: dict[str, Any] = {}
        exp_results: dict[str, Any] | None = None
        review_content = ""

        for stage in CAMPAIGN_STAGES[start_idx:]:
            camp_store.advance_stage(campaign_id, stage)
            campaign = camp_store.get_campaign(campaign_id) or campaign
            _sync_task_for_stage(resolved_pid, stage, "in_progress")

            if stage == "S0_campaign":
                from server.skills.bridge import get_skills_bridge

                artifact = {
                    "summary": clean_message,
                    "title": campaign.get("title"),
                    "assumptions": campaign.get("assumptions"),
                }
                explore_path = get_skills_bridge().bootstrap_campaign_artifact(
                    resolved_pid, campaign,
                )
                artifact["explore_output"] = explore_path
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                yield StreamChunk(
                    type="artifact_saved",
                    content=str(
                        campaign_artifacts_dir(resolved_pid, campaign_id) / f"{stage}.json"
                    ),
                    agent_name="supervisor",
                    a2a_task_id=a2a_task_id,
                )
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail="S0 立项完成")
                continue

            if stage == "S1_literature":
                prompt = (
                    f"{context_prefix}\n\n"
                    f"请检索与下列问题相关的损失函数/局部极小值/PL 条件文献，"
                    f"给出简短背景综述（3-5 篇）：\n\n{clean_message}"
                )
                content_acc = ""
                async for chunk in self._stage(
                    stage, "literature", prompt, session_id, a2a_task_id, **run_kwargs,
                ):
                    if chunk.type == "content":
                        content_acc += chunk.content
                    yield chunk
                refs = len(re.findall(r"arXiv:\d+\.\d+", content_acc, re.I))
                refs += len(re.findall(r"\[\d+\]", content_acc))
                artifact = {
                    "summary": _truncate(content_acc, 4000),
                    "reference_count": max(refs, 1 if content_acc.strip() else 0),
                }
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                gate_status, reason = _check_gate(stage, artifact, None)
                camp_store.update_gate(campaign_id, stage, "pass" if gate_status == "pass" else "fail")
                yield await self._emit_gate(stage, gate_status, reason, a2a_task_id)
                _sync_task_for_stage(
                    resolved_pid, stage, "done" if gate_status == "pass" else "blocked",
                )
                context = _build_context_pack(camp_store.get_campaign(campaign_id) or campaign)
                context_prefix = _format_context_prompt(context)
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail=reason)
                continue

            if stage == "S2_formalization":
                prompt = (
                    f"{context_prefix}\n\n"
                    f"请将下列研究问题形式化：列出符号、依赖假设（A1–A6 编号）、"
                    f"问题陈述与待证命题。\n\n{clean_message}"
                )
                content_acc = ""
                async for chunk in self._stage(
                    stage, "theory", prompt, session_id, a2a_task_id,
                    mode="math", **run_kwargs,
                ):
                    if chunk.type == "content":
                        content_acc += chunk.content
                    yield chunk
                artifact = {"summary": _truncate(content_acc, 4000)}
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                path = DATA_ROOT / "theory" / "campaigns" / f"{campaign_id}-problem.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content_acc or clean_message, encoding="utf-8")
                yield StreamChunk(
                    type="artifact_saved",
                    content=str(path),
                    agent_name="supervisor",
                    a2a_task_id=a2a_task_id,
                )
                context = _build_context_pack(camp_store.get_campaign(campaign_id) or campaign)
                context_prefix = _format_context_prompt(context)
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail="S2 形式化完成")
                continue

            if stage == "S3_theory":
                prompt = (
                    f"{context_prefix}\n\n"
                    f"在以上背景与问题陈述基础上，给出引理/定理链与证明（标注假设编号）。\n\n"
                    f"{clean_message}"
                )
                async for chunk in self._stage(
                    stage, "theory", prompt, session_id, a2a_task_id,
                    mode="math", **run_kwargs,
                ):
                    if chunk.type == "content":
                        theory_content += chunk.content
                    elif chunk.type == "verification_result":
                        try:
                            sympy_result = json.loads(chunk.content)
                        except json.JSONDecodeError:
                            pass
                    yield chunk
                artifact = {
                    "summary": _truncate(theory_content, 4000),
                    "verification_status": sympy_result.get("status", "unknown"),
                }
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                gate_status, reason = _check_gate(stage, artifact, None)
                camp_store.update_gate(
                    campaign_id, stage,
                    "pass" if gate_status in ("pass", "partial_pass") else "fail",
                )
                yield await self._emit_gate(stage, gate_status, reason, a2a_task_id)
                _sync_task_for_stage(
                    resolved_pid, stage, "done" if gate_status != "fail" else "blocked",
                )
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail=reason)
                continue

            if stage == "S4_counterexample":
                prompt = (
                    f"{context_prefix}\n\n"
                    f"针对以下理论推导，搜索假设失效时的反例或边界情形，"
                    f"写入 ## 反例 标题并指明失效假设。\n\n"
                    f"{_truncate(theory_content or clean_message, 3500)}"
                )
                content_acc = ""
                async for chunk in self._stage(
                    stage, "counterexample", prompt, session_id, a2a_task_id,
                    mode="math", **run_kwargs,
                ):
                    if chunk.type == "content":
                        content_acc += chunk.content
                    yield chunk
                counter_dir = DATA_ROOT / "theory" / "counterexamples"
                counter_dir.mkdir(parents=True, exist_ok=True)
                counter_path = counter_dir / f"{campaign_id}.md"
                counter_path.write_text(content_acc or "（无反例）", encoding="utf-8")
                artifact = {
                    "summary": _truncate(content_acc, 2000),
                    "path": str(counter_path),
                }
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                yield StreamChunk(
                    type="artifact_saved",
                    content=str(counter_path),
                    agent_name="supervisor",
                    a2a_task_id=a2a_task_id,
                )
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail="S4 反例完成")
                continue

            if stage == "S5_experiment":
                # 必须 await：禁止同步嵌套 event loop 调用主循环 MCP（会死锁）
                exp_results = await run_campaign_experiments(
                    theory_content or clean_message,
                    session_id=session_id,
                    campaign=campaign,
                )
                yield StreamChunk(
                    type="numerical_verification_result",
                    content=json.dumps(exp_results.get("summary", exp_results), ensure_ascii=False),
                    agent_name="experiment",
                    a2a_task_id=a2a_task_id,
                )
                exp_prompt = (
                    f"{context_prefix}\n\n"
                    f"请解读以下实验结果并补充 loss landscape 分析：\n"
                    f"{json.dumps(exp_results, ensure_ascii=False)[:2500]}"
                )
                content_acc = ""
                async for chunk in self._stage(
                    stage, "experiment", exp_prompt, session_id, a2a_task_id, **run_kwargs,
                ):
                    if chunk.type == "content":
                        content_acc += chunk.content
                    yield chunk
                artifact = {
                    "summary": content_acc or json.dumps(exp_results.get("summary", {})),
                    "runs": exp_results.get("runs", []),
                    "quadratic_pass": exp_results.get("quadratic_pass"),
                    "width_scaling_pass": exp_results.get("width_scaling_pass"),
                }
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                gate_status, reason = _check_gate(stage, artifact, exp_results)
                camp_store.update_gate(
                    campaign_id, stage,
                    "pass" if gate_status == "pass" else "fail",
                )
                yield await self._emit_gate(stage, gate_status, reason, a2a_task_id)
                _sync_task_for_stage(
                    resolved_pid, stage, "done" if gate_status == "pass" else "blocked",
                )
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail=reason)
                continue

            if stage == "S6_synthesis":
                prompt = (
                    f"{context_prefix}\n\n"
                    f"请综合文献、理论、反例与实验，撰写技术报告摘要（含主要定理与验证结论）。\n\n"
                    f"理论节选：\n{_truncate(theory_content, 2000)}"
                )
                content_acc = ""
                async for chunk in self._stage(
                    stage, "general", prompt, session_id, a2a_task_id, **run_kwargs,
                ):
                    if chunk.type == "content":
                        content_acc += chunk.content
                    yield chunk
                report_path = campaign_artifacts_dir(resolved_pid, campaign_id) / "report.md"
                report_path.write_text(content_acc, encoding="utf-8")
                artifact = {"summary": _truncate(content_acc, 4000), "path": str(report_path)}
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                yield StreamChunk(
                    type="artifact_saved",
                    content=str(report_path),
                    agent_name="supervisor",
                    a2a_task_id=a2a_task_id,
                )
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail="S6 综合完成")
                continue

            if stage == "S7_review":
                prompt = (
                    f"请对照审稿清单审查以下推导与实验，给出审稿意见（标注致命/主要/次要）：\n\n"
                    f"{_truncate(theory_content or clean_message, 4000)}"
                )
                async for chunk in self._stage(
                    stage, "review", prompt, session_id, a2a_task_id, **run_kwargs,
                ):
                    if chunk.type == "content":
                        review_content += chunk.content
                    yield chunk
                artifact = {"summary": _truncate(review_content, 4000)}
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                gate_status, reason = _check_gate(stage, artifact, None)
                camp_store.update_gate(
                    campaign_id, stage,
                    "pass" if gate_status == "pass" else "fail",
                )
                yield await self._emit_gate(stage, gate_status, reason, a2a_task_id)
                _sync_task_for_stage(
                    resolved_pid, stage, "done" if gate_status == "pass" else "blocked",
                )
                if gate_status == "fail":
                    camp_store.update_campaign(campaign_id, status="iterate")
                    campaign = camp_store.get_campaign(campaign_id) or campaign
                    yield await self._emit_campaign_update(
                        campaign, a2a_task_id, detail="审稿未通过，标记 iterate",
                    )
                    break
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail=reason)
                continue

            if stage == "S8_archive":
                camp_store.update_campaign(campaign_id, status="done", current_stage="complete")
                proj_store.append_audit(
                    resolved_pid,
                    "campaign_complete",
                    payload={"campaign_id": campaign_id},
                )
                artifact = {
                    "summary": "Campaign 已归档",
                    "gates": (camp_store.get_campaign(campaign_id) or {}).get("gates", {}),
                }
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                campaign = camp_store.get_campaign(campaign_id) or campaign
                yield await self._emit_campaign_update(campaign, a2a_task_id, detail="S8 归档完成")
                continue

        yield StreamChunk(
            type="pipeline_stage",
            content="complete",
            agent_name="supervisor",
            a2a_task_id=a2a_task_id,
            title="研究流水线完成",
            status="done",
        )
        final = camp_store.get_campaign(campaign_id) or campaign
        yield await self._emit_campaign_update(final, a2a_task_id, detail="流水线结束")


__all__ = ["ResearchSupervisorPipeline", "should_use_research_pipeline"]

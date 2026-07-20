# =============================================================================
# 科研 Supervisor 流水线：8 阶段 Campaign 编排。
#
# 职责：
#     1. 管理 S0–S8 Campaign 阶段推进、门禁与上下文传递
#     2. 各阶段委派 SubAgent 并写入 campaign 产物目录
#     3. S5 调用 campaign_experiments；S8 归档与收尾
#
# 架构位置：
#     - 被调用：server/agents/orchestrator.py（/research 路径）
#     - 调用：server/agents/subagent.py、memory/campaigns.py、projects.py、
#             experiments/campaign_experiments.py、graph/research_pipeline.py
#
# 阅读提示：
#     - 新人先看 ResearchSupervisorPipeline.execute() 主循环
#     - 阶段映射见 _STAGE_PIPELINE_NAMES 与 CAMPAIGN_STAGES
#
# Debug：
#     - 阶段 blocked → gates 字段或上一阶段产物缺失
#     - 重复开 Campaign → /research new 与普通 /research 行为不同
#     - 实验未跑 → S5 门禁或 theory_content 无 loss 表达式
# =============================================================================

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
        parts.append(f"【文献摘要】\n{_truncate(str(lit['summary']), 1500)}")
    prob = context.get("problem_statement") or {}
    if prob.get("summary"):
        parts.append(f"【问题陈述】\n{_truncate(str(prob['summary']), 1500)}")
    theory = context.get("theory_summary") or {}
    if theory.get("summary"):
        parts.append(f"【已有理论】\n{_truncate(str(theory['summary']), 2000)}")
    counter = context.get("counterexample_summary") or {}
    if counter.get("summary"):
        parts.append(f"【反例】\n{_truncate(str(counter['summary']), 1200)}")
    exp = context.get("experiment_summary") or {}
    if exp.get("summary"):
        parts.append(f"【实验】\n{_truncate(str(exp['summary']), 1200)}")
    return "\n\n".join(parts)


def _wrapup_user_prompt(clean_message: str, campaign: dict[str, Any]) -> tuple[str, str]:
    """已完成 Campaign 的收尾提示。

    返回 (短用户句, 系统侧产物上下文)。
    短用户句写入会话历史，避免每次收尾把整包产物再塞进 L1。
    """
    context = _build_context_pack(campaign)
    context_block = _format_context_prompt(context)
    user_part = (clean_message or "").strip()
    bootstrap_phrases = (
        "请对损失函数局部极小值进行完整研究",
        "对损失函数局部极小值进行完整研究",
    )
    if not user_part or user_part in bootstrap_phrases or user_part.startswith("请对损失函数"):
        user_part = (
            "请对本课题已完成研究进行收尾总结："
            "汇总定理/引理状态、反例、实验结论与开放问题，给出最终结论。"
            "不要重新从文献检索或形式化阶段开始。"
        )
    system_extra = (
        "【收尾模式】Campaign 已结束；只做收尾综合，不要重启 S0–S7 流水线。\n\n"
        f"{context_block}"
    )
    return user_part, system_extra


def _check_gate(stage: str, artifact: dict[str, Any], exp_results: dict[str, Any] | None) -> tuple[str, str]:
    """返回 (status, reason)。status: pass|fail|skipped|partial_pass"""
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
        return _check_review_gate(str(artifact.get("summary", "")))

    return "skipped", "无门禁"


def _check_review_gate(text: str) -> tuple[str, str]:
    """审稿门禁：避免把「致命问题已修复」误判为 fail。"""
    import re

    text = (text or "").strip()
    if not text:
        return "fail", "审稿未产出意见"

    lower = text.lower()
    pass_markers = (
        "有条件通过",
        "审稿建议**：通过",
        "审稿建议:**通过",
        "审稿建议：通过",
        "建议接受",
        "建议：通过",
        "recommendation: accept",
        "accept with minor",
        "minor revision",
    )
    if any(m in text or m in lower for m in pass_markers):
        return "pass", "审稿完成（建议通过）"

    unresolved_markers = (
        "仍存在致命",
        "尚有致命",
        "仍有致命",
        "存在致命缺陷",
        "发现致命缺陷",
        "致命缺陷未",
        "fatal flaw",
        "major flaw",
    )
    if any(m in text or m in lower for m in unresolved_markers):
        return "fail", "审稿发现未解决的致命缺陷"

    # 逐句看「致命」：历史回顾 / 已修复 → 忽略；当前仍判定有致命 → fail
    for part in re.split(r"[。！？\n；;]", text):
        if "致命" not in part and "严重缺陷" not in part:
            continue
        if any(
            x in part
            for x in ("已修复", "已解决", "已处理", "已消除", "不存在", "没有", "无致命", "均已")
        ):
            continue
        if any(x in part for x in ("第一轮", "上轮", "此前", "指出的致命", "曾有致命")):
            continue
        return "fail", "审稿发现致命缺陷"

    return "pass", "审稿完成"


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
        *,
        force_new: bool = False,
        prefer_open: bool = True,
    ) -> dict[str, Any]:
        store = get_campaign_store()
        if not force_new:
            camp = store.get_active_campaign(
                project_id, campaign_id, session_id=session_id, prefer_open=prefer_open,
            )
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

    def _campaign_finished(self, campaign: dict[str, Any]) -> bool:
        stage = str(campaign.get("current_stage") or "")
        return campaign.get("status") == "done" or stage in ("complete", "S8_archive")

    @staticmethod
    def _is_wrapup_intent(message: str, clean_message: str) -> bool:
        text = f"{message}\n{clean_message}"
        return any(
            kw in text
            for kw in ("收尾", "总结研究", "研究总结", "归档", "结题", "最终结论", "不要重新开跑")
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
        """
        执行 8 阶段 Campaign 主管道，按当前阶段委派 SubAgent 并更新门禁。

        参数:
            message: 用户输入（/research 前缀会触发 Campaign 逻辑）
            session_id: 会话 ID
            project_id / campaign_id: 课题与 Campaign 上下文
            run_kwargs: 透传给 SubAgent.run 的推理与工具选项

        返回:
            StreamChunk 异步迭代器
        """
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
        explicit_new = message.strip().startswith("/research")
        # 仅「/research new」或「/research 重新开始」才强制新开；普通 /research 在已完成时走收尾对话
        force_restart = bool(
            re.match(
                r"^/research\s+(new|重新开始|重启)\b",
                message.strip(),
                flags=re.IGNORECASE,
            )
        )
        wrapup_intent = self._is_wrapup_intent(message, clean_message) and not force_restart
        # 收尾：按「展示进度最深」解析，避免未绑定会话的浅层测试 Campaign 抢走已完成课题
        campaign = self._resolve_campaign(
            resolved_pid,
            campaign_id,
            session_id,
            clean_message,
            prefer_open=not wrapup_intent,
        )
        if (
            not force_restart
            and not self._campaign_finished(campaign)
            and campaign_id is None
        ):
            # UI 以 prefer_open=False 展示已完成体；执行侧若误拿到浅层 active，改绑到更深的已完成 Campaign
            from server.memory.campaigns import campaign_stage_rank

            display = camp_store.get_active_campaign(
                resolved_pid, prefer_open=False,
            )
            if (
                display
                and self._campaign_finished(display)
                and campaign_stage_rank(display.get("current_stage"))
                > campaign_stage_rank(campaign.get("current_stage"))
            ):
                logger.info(
                    "课题 %s 已有完成 Campaign %s，忽略浅层 %s（%s/%s）",
                    resolved_pid,
                    display.get("id"),
                    campaign.get("id"),
                    campaign.get("status"),
                    campaign.get("current_stage"),
                )
                campaign = display
                if session_id and not campaign.get("session_id"):
                    camp_store.update_campaign(campaign["id"], session_id=session_id)
                    campaign = camp_store.get_campaign(campaign["id"]) or campaign

        if self._campaign_finished(campaign) and force_restart and campaign_id is None:
            campaign = self._resolve_campaign(
                resolved_pid, None, session_id, clean_message, force_new=True,
            )
        elif self._campaign_finished(campaign) and explicit_new and campaign_id is None:
            # 兼容旧行为提示：不再静默开新 Campaign，避免进度「回退」到 S0/S1
            logger.info(
                "Campaign %s 已完成；普通 /research 不新开，改走收尾对话"
                "（需要新开请用 /research new）",
                campaign.get("id"),
            )
        campaign_id = campaign["id"]
        yield await self._emit_campaign_update(
            campaign, a2a_task_id, detail="Campaign 已加载",
        )

        # 已完成的 Campaign：注入产物上下文，走普通 Agent 收尾（禁止空跑 S8 / 重开流水线）
        if self._campaign_finished(campaign):
            logger.info(
                "Campaign %s 已结束(%s/%s)，改走普通对话收尾",
                campaign_id,
                campaign.get("status"),
                campaign.get("current_stage"),
            )
            # 收尾固定 general：避免 Math/theory + thinking 在残缺历史上触发
            # DeepSeek「reasoning_content must be passed back」400
            agent_name: AgentName = "general"
            yield StreamChunk(
                type="agent_handoff",
                content="campaign_complete_fallback",
                from_agent="supervisor",
                to_agent=agent_name,
                route_reason="campaign_complete_fallback",
                agent_name=agent_name,
                a2a_task_id=a2a_task_id,
            )
            # 立刻给前端可见反馈，避免长时间停在「正在生成…」像卡死
            yield StreamChunk(
                type="content",
                content="正在根据已完成产物生成收尾报告…\n\n",
                agent_name=agent_name,
                a2a_task_id=a2a_task_id,
            )
            wrap_user, wrap_system_extra = _wrapup_user_prompt(clean_message, campaign)
            agent = self._get_agent(agent_name)
            system_override = (
                f"{agent.system_prompt}\n\n{wrap_system_extra}\n\n"
                "输出要求：用简洁中文给出定理/反例/实验/开放问题与最终结论；"
                "不要调用工具；不要输出冗长思维链小节。"
            )
            # 轻量收尾：关 thinking/工具/RAG/L4 注入，不带历史，避免慢与 400
            wrap_kwargs = {
                **run_kwargs,
                "enable_thinking": False,
                "enable_tools": False,
                "enable_rag": False,
                "augment_structured_memory": False,
                "max_history_messages": -1,
                "cot_mode": "off",
                "system_prompt_override": system_override,
            }
            async for chunk in agent.run(
                wrap_user,
                session_id,
                a2a_task_id=a2a_task_id,
                **wrap_kwargs,
            ):
                yield chunk
            return

        start_idx = _stage_index(str(campaign.get("current_stage", "S0_campaign")))
        if str(campaign.get("current_stage") or "") == "complete":
            start_idx = len(CAMPAIGN_STAGES)
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
                artifact = {
                    "summary": "Campaign 已归档",
                    "gates": (camp_store.get_campaign(campaign_id) or {}).get("gates", {}),
                }
                camp_store.save_stage_artifact(campaign_id, stage, artifact)
                # save_stage_artifact 会把 current_stage 写成 S8；归档后再标为 complete
                camp_store.update_campaign(
                    campaign_id, status="done", current_stage="complete",
                )
                proj_store.append_audit(
                    resolved_pid,
                    "campaign_complete",
                    payload={"campaign_id": campaign_id},
                )
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

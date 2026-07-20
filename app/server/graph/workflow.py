# =============================================================================
# 工作流思维链 SSE 辅助函数。
#
# 职责：
#     1. 生成 plan / tool / verify / synthesize 步骤的 StreamChunk
#     2. 维护 stable_step_id 供前端合并 running→done 状态
#     3. upsert / finalize workflow 记录供持久化与回放
#
# 架构位置：
#     - 被调用：server/agents/base.py、subagent.py、graph/theory_pipeline.py
#     - 调用：shared/schemas.StreamChunk
#
# 阅读提示：
#     - 新人先看 workflow_step_chunk 与 stable_step_id
#
# Debug：
#     - 前端步骤卡住 → step id 不稳定或 status 未从 running 变为 done
# =============================================================================

from __future__ import annotations

import json
from typing import Literal

from shared.schemas import StreamChunk

WorkflowKind = Literal["plan", "tool", "verify", "synthesize"]
WorkflowStatus = Literal["running", "done", "pass", "fail", "skipped", "error"]

# 稳定 ID：前端按此合并 running→done，避免标题变化导致「进行中」卡住
STABLE_STEP_IDS: dict[str, str] = {
    "plan": "wf-plan",
    "synthesize": "wf-synthesize",
    "verify": "wf-verify",
}


def stable_step_id(step_kind: str, tool_call_id: str | None = None) -> str:
    if tool_call_id:
        return tool_call_id
    return STABLE_STEP_IDS.get(step_kind, f"wf-{step_kind}")


def workflow_step_chunk(
    step_kind: WorkflowKind,
    *,
    status: WorkflowStatus = "running",
    title: str,
    detail: str = "",
    agent_name: str | None = None,
    a2a_task_id: str | None = None,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
) -> StreamChunk:
    """构造 workflow_step SSE 事件。"""
    return StreamChunk(
        type="workflow_step",
        content=detail,
        step_kind=step_kind,
        status=status,
        title=title,
        detail=detail or None,
        agent_name=agent_name,
        a2a_task_id=a2a_task_id,
        tool_name=tool_name,
        tool_call_id=stable_step_id(step_kind, tool_call_id),
    )


def workflow_step_record(
    step_kind: WorkflowKind,
    *,
    status: WorkflowStatus,
    title: str,
    detail: str = "",
    tool_name: str | None = None,
    tool_call_id: str | None = None,
) -> dict:
    """可持久化到 messages.workflow_steps 的字典。"""
    return {
        "step_kind": step_kind,
        "status": status,
        "title": title,
        "detail": detail,
        "tool_name": tool_name,
        "tool_call_id": stable_step_id(step_kind, tool_call_id),
    }


def _record_step_key(record: dict) -> tuple[str, str]:
    kind = str(record.get("step_kind") or "")
    tid = record.get("tool_call_id") or STABLE_STEP_IDS.get(kind) or f"wf-{kind}"
    return kind, str(tid)


def upsert_workflow_record(records: list[dict], record: dict) -> None:
    """按 step_kind（及 tool_call_id）原地更新，并清掉同 key 的重复 running 残留。"""
    kind, tid = _record_step_key(record)
    normalized = {**record, "tool_call_id": tid}
    matched = False
    i = 0
    while i < len(records):
        existing = records[i]
        if _record_step_key(existing) != (kind, tid):
            i += 1
            continue
        if not matched:
            records[i] = normalized
            matched = True
            i += 1
        else:
            del records[i]
    if not matched:
        records.append(normalized)


def finalize_workflow_records(records: list[dict] | None) -> list[dict] | None:
    """落库前兜底：合并同 key，并把仍为 running 的步骤标为 done。"""
    if not records:
        return records
    collapsed: list[dict] = []
    for record in records:
        upsert_workflow_record(collapsed, record)
    finalized: list[dict] = []
    for record in collapsed:
        if record.get("status") == "running":
            finalized.append(
                {
                    **record,
                    "status": "done",
                    "detail": record.get("detail") or "已结束",
                }
            )
        else:
            finalized.append(record)
    return finalized


def cot_step_chunks(content: str, *, agent_name: str | None = None) -> list[StreamChunk]:
    """从完整回答正文解析并生成 cot_step SSE 事件列表。"""
    from server.llm.cot_parser import parse_cot_sections

    chunks: list[StreamChunk] = []
    for step in parse_cot_sections(content):
        payload = json.dumps(
            {"step": step.step, "title": step.title, "body": step.body},
            ensure_ascii=False,
        )
        chunks.append(
            StreamChunk(
                type="cot_step",
                content=payload,
                agent_name=agent_name,
                title=step.title,
            ),
        )
    return chunks

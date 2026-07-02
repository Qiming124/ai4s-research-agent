# 工作流思维链 SSE 辅助函数。

from __future__ import annotations

import json
from typing import Literal

from shared.schemas import StreamChunk

WorkflowKind = Literal["plan", "tool", "verify", "synthesize"]
WorkflowStatus = Literal["running", "done", "pass", "fail", "skipped", "error"]


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
        tool_call_id=tool_call_id,
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
        "tool_call_id": tool_call_id,
    }


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

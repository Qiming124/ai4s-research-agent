# =============================================================================
# LangGraph 工具循环 + 最终流式回答 → StreamChunk SSE 映射。
#
# 职责：
#     1. 运行 ReAct 子图（astream 消费节点更新）
#     2. 将节点头部的 tool_call_start / tool_call_result / tool_call_error 转为 SSE StreamChunk
#     3. 工具循环结束后，用 final_model 流式生成最终回答（含 reasoning）
#     4. 从 AIMessageChunk 中提取 reasoning_content（DeepSeek thinking 模式）
#
# 架构位置：
#     GeneralAgent._run_langgraph_tool_loop → stream_react_graph
#     产物直接 yield 给 SSE 端点
# =============================================================================

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from server.graph.workflow import (
    upsert_workflow_record,
    workflow_step_chunk,
    workflow_step_record,
)
from shared.schemas import PersistedToolCall, StreamChunk

logger = logging.getLogger(__name__)


def _extract_reasoning(chunk: AIMessageChunk | AIMessage) -> str:
    """
    从 LangChain AIMessageChunk 中提取 DeepSeek reasoning_content。

    DeepSeek 的 thinking 内容不在 standard content 字段，
    而是附加在 additional_kwargs["reasoning_content"] 或
    response_metadata["reasoning_content"] 中。

    返回:
        空字符串表示本 chunk 无 reasoning 内容，或 reasoning 内容字符串
    """
    # 途径 1：additional_kwargs（流式中间 chunk）
    additional = getattr(chunk, "additional_kwargs", None) or {}
    reasoning = additional.get("reasoning_content")
    if reasoning:
        return str(reasoning)
    # 途径 2：response_metadata（最终 message）
    response_metadata = getattr(chunk, "response_metadata", None) or {}
    reasoning = response_metadata.get("reasoning_content")
    return str(reasoning) if reasoning else ""


def _usage_from_message(message: AIMessage | AIMessageChunk) -> dict[str, Any] | None:
    """
    从 LangChain message 中提取 token 用量统计。

    DeepSeek API 用量可能存放在：
        - response_metadata["token_usage"]
        - response_metadata["usage"]
    """
    metadata = getattr(message, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage")
    if token_usage:
        return dict(token_usage)
    usage = metadata.get("usage")
    return dict(usage) if usage else None


async def stream_react_graph(
    graph: Any,
    inputs: dict[str, Any],
    *,
    final_model: BaseChatModel,
    agent_name: str,
    max_tool_rounds: int,
    workflow_records: list[dict] | None = None,
) -> AsyncIterator[tuple[StreamChunk, list[PersistedToolCall] | None]]:
    """
    运行 ReAct 工具子图，流式产出 SSE StreamChunk。

    流程：
        1. 用 graph.astream 消费 call_model / execute_tools 节点更新
        2. call_model 产出 tool_calls → yield tool_call_start SSE 事件
        3. execute_tools 产出 tool_call_records → yield tool_call_result / tool_call_error
        4. 工具循环结束后，用 final_model 流式生成最终回答
        5. 从流式 chunk 中提取 reasoning_content → yield reasoning 事件
        6. 全部回答产出后 → yield done 事件

    参数:
        graph: 编译后的 ReAct StateGraph（来自 build_react_graph）
        inputs: {"messages": BaseMessage列表, "tool_call_records": [], "tool_rounds": 0}
        final_model: thinking=enabled 的 ChatOpenAI 模型（最终回答用）
        agent_name: 当前 Agent 名（填入 StreamChunk.agent_name）
        max_tool_rounds: 工具调用轮次上限（用于日志）

    产出:
        (StreamChunk, list[PersistedToolCall] | None) 二元组
        PersistedToolCall 列表在工具完成时随 done 事件的 chunk 一起产出，
        调用方用于写入会话。
    """
    all_records: list[PersistedToolCall] = []
    seen_record_ids: set[str] = set()  # 去重：同一 tool_call 可能多次更新
    messages: list[BaseMessage] = list(inputs.get("messages", []))
    usage: dict[str, Any] | None = None
    early_content: str | None = None  # 工具轮次中可能已有 content（无 tool_calls 子图终止）
    wf_records = workflow_records if workflow_records is not None else []

    yield (
        workflow_step_chunk(
            "plan",
            status="running",
            title="分析问题并规划工具调用",
            agent_name=agent_name,
        ),
        None,
    )
    upsert_workflow_record(
        wf_records,
        workflow_step_record(
            "plan",
            status="running",
            title="分析问题并规划工具调用",
        ),
    )

    # ── 第一步：流式运行 ReAct 子图（call_model ↔ execute_tools） ──
    async for update in graph.astream(inputs, stream_mode="updates"):
        # 处理 call_model 节点产出
        if "call_model" in update:
            node_out = update["call_model"]
            if node_out.get("messages"):
                messages.extend(node_out["messages"])
            last = messages[-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                # LLM 请求了工具 → 逐条产出 tool_call_start SSE 事件
                for tc in last.tool_calls:
                    args_json = json.dumps(tc.get("args") or {}, ensure_ascii=False)
                    yield (
                        StreamChunk(
                            type="tool_call_start",
                            content=args_json,
                            tool_name=tc["name"],
                            tool_call_id=tc["id"],
                            agent_name=agent_name,
                        ),
                        None,
                    )
            elif isinstance(last, AIMessage) and last.content and not last.tool_calls:
                # LLM 已给出直接回答（后续不再调工具）
                early_content = str(last.content)
                usage = _usage_from_message(last)

        # 处理 execute_tools 节点产出
        if "execute_tools" in update:
            node_out = update["execute_tools"]
            if node_out.get("messages"):
                messages.extend(node_out["messages"])
            new_records = node_out.get("tool_call_records") or []
            for record in new_records:
                if record.id in seen_record_ids:
                    continue  # 重复 record，跳过
                seen_record_ids.add(record.id)
                all_records.append(record)
                if record.status == "error":
                    yield (
                        StreamChunk(
                            type="tool_call_error",
                            content=record.error or "工具调用失败",
                            tool_name=record.name,
                            tool_call_id=record.id,
                            agent_name=agent_name,
                        ),
                        None,
                    )
                else:
                    yield (
                        StreamChunk(
                            type="tool_call_result",
                            content=record.result or "",
                            tool_name=record.name,
                            tool_call_id=record.id,
                            agent_name=agent_name,
                        ),
                        None,
                    )

    # ── 第二步：子图已结束处理 ──

    # 规划阶段结束（无论是否实际调用了工具，都要关闭「进行中」）
    yield (
        workflow_step_chunk(
            "plan",
            status="done",
            title="分析问题并规划工具调用",
            detail="工具规划完成" if all_records else "无需调用工具",
            agent_name=agent_name,
        ),
        None,
    )
    upsert_workflow_record(
        wf_records,
        workflow_step_record(
            "plan",
            status="done",
            title="分析问题并规划工具调用",
            detail="工具规划完成" if all_records else "无需调用工具",
        ),
    )

    # 若子图在工具轮次中已产出最终 content（非工具调用情况）
    if early_content is not None:
        yield (
            StreamChunk(type="content", content=early_content, agent_name=agent_name),
            all_records or None,
        )
        yield (
            StreamChunk(type="done", content="", usage=usage, agent_name=agent_name),
            None,
        )
        return

    # 工具轮次达到上限时的警告
    if all_records and len(all_records) >= max_tool_rounds:
        logger.warning(
            "MCP 工具调用轮次达到上限 (%d)，将基于已有结果生成回答",
            max_tool_rounds,
        )

    # ── 第三步：用 final_model 流式生成最终回答（含 reasoning） ──
    yield (
        workflow_step_chunk(
            "synthesize",
            status="running",
            title="综合信息并生成回答",
            agent_name=agent_name,
        ),
        None,
    )
    upsert_workflow_record(
        wf_records,
        workflow_step_record(
            "synthesize",
            status="running",
            title="综合信息并生成回答",
        ),
    )

    full_content = ""
    full_reasoning = ""
    async for chunk in final_model.astream(messages):
        if isinstance(chunk, AIMessageChunk):
            # 提取 reasoning_content（DeepSeek thinking 模式）
            reasoning = _extract_reasoning(chunk)
            if reasoning:
                # 只取增量：reasoning 可能重复累积，需对全长求 diff
                delta = reasoning[len(full_reasoning):]
                if delta:
                    full_reasoning = reasoning
                    yield (
                        StreamChunk(type="reasoning", content=delta, agent_name=agent_name),
                        None,
                    )
            content = chunk.content
            if isinstance(content, str) and content:
                # 去重: 第二个 chunk 可能从头开始包含第一个 chunk 的内容
                if full_content and content.startswith(full_content):
                    delta = content[len(full_content):]
                    full_content = content
                else:
                    delta = content
                    full_content += delta
                if delta:
                    yield (
                        StreamChunk(type="content", content=delta, agent_name=agent_name),
                        None,
                    )
        elif isinstance(chunk, AIMessage):
            # 最终 message 可能含 token 用量
            usage = _usage_from_message(chunk) or usage

    upsert_workflow_record(
        wf_records,
        workflow_step_record("synthesize", status="done", title="综合信息并生成回答", detail="回答生成完成"),
    )
    yield (
        workflow_step_chunk(
            "synthesize",
            status="done",
            title="综合信息并生成回答",
            detail="回答生成完成",
            agent_name=agent_name,
        ),
        None,
    )

    # ── 第四步：发送 done 事件（含累积工具记录与 token 用量） ──
    yield (
        StreamChunk(type="done", content="", usage=usage, agent_name=agent_name),
        all_records or None,
    )

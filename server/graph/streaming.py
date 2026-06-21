# LangGraph 工具循环 + 最终流式回答 → StreamChunk SSE 映射。

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from shared.schemas import PersistedToolCall, StreamChunk

logger = logging.getLogger(__name__)


def _extract_reasoning(chunk: AIMessageChunk | AIMessage) -> str:
    additional = getattr(chunk, "additional_kwargs", None) or {}
    reasoning = additional.get("reasoning_content")
    if reasoning:
        return str(reasoning)
    response_metadata = getattr(chunk, "response_metadata", None) or {}
    reasoning = response_metadata.get("reasoning_content")
    return str(reasoning) if reasoning else ""


def _usage_from_message(message: AIMessage | AIMessageChunk) -> dict[str, Any] | None:
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
) -> AsyncIterator[tuple[StreamChunk, list[PersistedToolCall] | None]]:
    """运行 ReAct 工具子图，再流式生成最终回答（含 reasoning）。"""
    all_records: list[PersistedToolCall] = []
    seen_record_ids: set[str] = set()
    messages: list[BaseMessage] = list(inputs.get("messages", []))
    usage: dict[str, Any] | None = None
    early_content: str | None = None

    async for update in graph.astream(inputs, stream_mode="updates"):
        if "call_model" in update:
            node_out = update["call_model"]
            if node_out.get("messages"):
                messages.extend(node_out["messages"])
            last = messages[-1]
            if isinstance(last, AIMessage) and last.tool_calls:
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
                early_content = str(last.content)
                usage = _usage_from_message(last)

        if "execute_tools" in update:
            node_out = update["execute_tools"]
            if node_out.get("messages"):
                messages.extend(node_out["messages"])
            new_records = node_out.get("tool_call_records") or []
            for record in new_records:
                if record.id in seen_record_ids:
                    continue
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

    if all_records and len(all_records) >= max_tool_rounds:
        logger.warning(
            "MCP 工具调用轮次达到上限 (%d)，将基于已有结果生成回答",
            max_tool_rounds,
        )

    full_content = ""
    full_reasoning = ""
    async for chunk in final_model.astream(messages):
        if isinstance(chunk, AIMessageChunk):
            reasoning = _extract_reasoning(chunk)
            if reasoning:
                delta = reasoning[len(full_reasoning):]
                if delta:
                    full_reasoning = reasoning
                    yield (
                        StreamChunk(type="reasoning", content=delta, agent_name=agent_name),
                        None,
                    )
            content = chunk.content
            if isinstance(content, str) and content:
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
            usage = _usage_from_message(chunk) or usage

    yield (
        StreamChunk(type="done", content="", usage=usage, agent_name=agent_name),
        all_records or None,
    )

# 参数化 ReAct 子 Agent：独立 prompt + 工具白名单。

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from server.agents.config import AgentName, get_agent_prompt
from server.config import Settings, get_settings
from server.graph.react import build_react_graph, messages_from_api_dicts
from server.graph.streaming import stream_react_graph
from server.langchain.llm import get_chat_model
from server.langchain.tools import mcp_tools_to_langchain
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.memory.base import BaseSessionStore
from server.memory.manager import MemoryManager, get_memory_manager
from server.memory.rag.retrieval import build_rag_augmented_prompt
from server.memory.session import SessionStore, get_session_store
from server.mcp.client import MCPClient, get_mcp_client
from server.mcp.truncation import truncate_tool_result
from server.observability import finalize_chat_turn, set_agent_name, set_session_id
from shared.schemas import ChatMessage, PersistedToolCall, StreamChunk

logger = logging.getLogger(__name__)

_TOOLS_SYSTEM_HINT = (
    "你可以使用提供的工具搜索网络、检索 arXiv 论文或读写实验日志文件。"
    "在需要外部信息时主动调用工具，并在回答中引用工具返回的内容。"
)


class SubAgent:
    """LangGraph ReAct 子图执行器，按 agent_name 绑定 prompt 与工具白名单。"""

    def __init__(
        self,
        name: AgentName,
        settings: Settings | None = None,
        llm_client: DeepSeekClient | None = None,
        session_store: SessionStore | None = None,
        memory_manager: MemoryManager | None = None,
        mcp_client: MCPClient | None = None,
        *,
        system_prompt: str | None = None,
    ) -> None:
        self.name = name
        self._settings = settings or get_settings()
        self._llm = llm_client or get_deepseek_client()
        self._sessions: BaseSessionStore = session_store or get_session_store()
        self._memory = memory_manager or get_memory_manager()
        self._mcp = mcp_client
        self.system_prompt = system_prompt or get_agent_prompt(name)

    def _with_agent(
        self,
        chunk: StreamChunk,
        *,
        a2a_task_id: str | None = None,
    ) -> StreamChunk:
        updates: dict[str, Any] = {"agent_name": self.name}
        if a2a_task_id:
            updates["a2a_task_id"] = a2a_task_id
        return chunk.model_copy(update=updates)

    def _build_messages(
        self,
        history: list[ChatMessage],
        user_message: str,
        system_prompt: str,
        *,
        enable_tools: bool = False,
    ) -> list[dict[str, Any]]:
        prompt = system_prompt
        if enable_tools:
            prompt = f"{prompt}\n\n{_TOOLS_SYSTEM_HINT}"
        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    async def _resolve_mcp(self) -> MCPClient | None:
        if not self._settings.enable_mcp:
            return None
        if self._mcp is not None:
            return self._mcp
        return await get_mcp_client()

    async def _run_langgraph_tool_loop(
        self,
        api_messages: list[dict[str, Any]],
        mcp: MCPClient,
        tool_call_records: list[PersistedToolCall],
        *,
        a2a_task_id: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        lc_tools = mcp_tools_to_langchain(mcp, agent_name=self.name)
        if not lc_tools:
            async for chunk in self._llm.stream_chat(api_messages):
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
            return

        tool_model = get_chat_model(self._settings, enable_thinking=False)
        final_model = get_chat_model(self._settings, enable_thinking=True)
        graph = build_react_graph(
            tool_model,
            lc_tools,
            max_tool_rounds=self._settings.mcp_max_tool_rounds,
            max_result_chars=self._settings.mcp_tool_result_max_chars,
        )
        inputs = {
            "messages": messages_from_api_dicts(api_messages),
            "tool_call_records": [],
            "tool_rounds": 0,
        }

        async for chunk, records in stream_react_graph(
            graph,
            inputs,
            final_model=final_model,
            agent_name=self.name,
            max_tool_rounds=self._settings.mcp_max_tool_rounds,
        ):
            if records:
                tool_call_records.extend(records)
            yield self._with_agent(chunk, a2a_task_id=a2a_task_id)

    async def _run_legacy_tool_loop(
        self,
        api_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        mcp: MCPClient,
        tool_call_records: list[PersistedToolCall],
        *,
        a2a_task_id: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        usage: dict[str, Any] | None = None
        max_result_chars = self._settings.mcp_tool_result_max_chars

        for _round in range(self._settings.mcp_max_tool_rounds):
            result = await self._llm.chat_with_tools(
                api_messages,
                tools,
                enable_thinking=False,
            )
            if result.usage:
                usage = result.usage

            if not result.tool_calls:
                if result.content:
                    yield self._with_agent(
                        StreamChunk(type="content", content=result.content),
                        a2a_task_id=a2a_task_id,
                    )
                    usage = result.usage or usage
                    yield self._with_agent(
                        StreamChunk(type="done", content="", usage=usage),
                        a2a_task_id=a2a_task_id,
                    )
                    return
                break

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in result.tool_calls
                ],
            }
            api_messages.append(assistant_msg)

            for tc in result.tool_calls:
                args_json = json.dumps(tc.arguments, ensure_ascii=False)
                yield self._with_agent(
                    StreamChunk(
                        type="tool_call_start",
                        content=args_json,
                        tool_name=tc.name,
                        tool_call_id=tc.id,
                    ),
                    a2a_task_id=a2a_task_id,
                )
                record = PersistedToolCall(
                    id=tc.id,
                    name=tc.name,
                    arguments=args_json,
                )
                try:
                    tool_result = await mcp.call_tool(tc.name, tc.arguments)
                    record.result = tool_result
                    record.status = "success"
                    yield self._with_agent(
                        StreamChunk(
                            type="tool_call_result",
                            content=tool_result,
                            tool_name=tc.name,
                            tool_call_id=tc.id,
                        ),
                        a2a_task_id=a2a_task_id,
                    )
                except Exception as exc:
                    err_text = f"工具调用失败: {exc}"
                    record.status = "error"
                    record.error = err_text
                    yield self._with_agent(
                        StreamChunk(
                            type="tool_call_error",
                            content=err_text,
                            tool_name=tc.name,
                            tool_call_id=tc.id,
                        ),
                        a2a_task_id=a2a_task_id,
                    )
                    tool_result = err_text

                tool_call_records.append(record)
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": truncate_tool_result(tool_result, max_result_chars),
                })
        else:
            logger.warning(
                "MCP 工具调用轮次达到上限 (%d)，将基于已有结果生成回答",
                self._settings.mcp_max_tool_rounds,
            )

        full_content = ""
        full_reasoning = ""
        async for chunk in self._llm.stream_chat(api_messages):
            if chunk.type == "reasoning":
                full_reasoning += chunk.content
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
            elif chunk.type == "content":
                full_content += chunk.content
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
            elif chunk.type == "error":
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
                return
            elif chunk.type == "done":
                if chunk.usage:
                    usage = chunk.usage
                yield self._with_agent(
                    StreamChunk(type="done", content="", usage=usage),
                    a2a_task_id=a2a_task_id,
                )
                return

        yield self._with_agent(StreamChunk(type="done", content="", usage=usage), a2a_task_id=a2a_task_id)

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
        a2a_task_id: str | None = None,
        persist_session: bool = True,
    ) -> AsyncIterator[StreamChunk]:
        sid = self._sessions.get_or_create(session_id)
        set_session_id(sid)
        set_agent_name(self.name)
        system_prompt = system_prompt_override or self.system_prompt

        if (
            self._settings.enable_rag
            and self.name in self._settings.rag_agent_names()
        ):
            system_prompt = build_rag_augmented_prompt(
                system_prompt,
                message,
                sid,
                self._settings,
            )

        full_history = self._sessions.get_messages(sid)
        history = await self._memory.get_llm_context(
            sid,
            max_messages=max_history_messages,
            enable_summary=enable_history_summary,
        )

        use_tools = (
            self._settings.enable_mcp
            if enable_tools is None
            else enable_tools
        )
        mcp = await self._resolve_mcp() if use_tools else None
        tools = (
            mcp.get_openai_tools(agent_name=self.name)
            if mcp and mcp.is_connected
            else []
        )
        effective_tools = use_tools and bool(tools)

        api_messages = self._build_messages(
            history,
            message,
            system_prompt,
            enable_tools=effective_tools,
        )

        logger.info(
            "SubAgent[%s] session=%s 全量历史=%d L1上下文=%d tools=%d",
            self.name,
            sid,
            len(full_history),
            len(history),
            len(tools),
        )

        full_content = ""
        full_reasoning = ""
        persisted_tool_calls: list[PersistedToolCall] = []

        if effective_tools and mcp is not None:
            use_langgraph = self._settings.orchestration_backend == "langgraph"
            if use_langgraph:
                tool_loop = self._run_langgraph_tool_loop
                tool_loop_args = (api_messages, mcp, persisted_tool_calls)
            else:
                tool_loop = self._run_legacy_tool_loop
                tool_loop_args = (api_messages, tools, mcp, persisted_tool_calls)

            async for chunk in tool_loop(
                *tool_loop_args,
                a2a_task_id=a2a_task_id,
            ):
                if chunk.type == "content":
                    full_content += chunk.content
                    yield chunk
                elif chunk.type == "reasoning":
                    full_reasoning += chunk.content
                    yield chunk
                elif chunk.type == "done":
                    if persist_session:
                        self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                        self._sessions.append_message(
                            sid,
                            ChatMessage(
                                role="assistant",
                                content=full_content,
                                reasoning_content=full_reasoning or None,
                                tool_calls=persisted_tool_calls or None,
                            ),
                        )
                    usage = chunk.usage or {}
                    usage["session_id"] = sid
                    finalize_chat_turn(sid, self.name, usage)
                    yield self._with_agent(
                        StreamChunk(type="done", content="", usage=usage),
                        a2a_task_id=a2a_task_id,
                    )
                    return
                elif chunk.type == "error":
                    yield chunk
                    return
                else:
                    yield chunk
            return

        async for chunk in self._llm.stream_chat(api_messages):
            if chunk.type == "reasoning":
                full_reasoning += chunk.content
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
            elif chunk.type == "content":
                full_content += chunk.content
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
            elif chunk.type == "error":
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
                return
            elif chunk.type == "done":
                if persist_session:
                    self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                    self._sessions.append_message(
                        sid,
                        ChatMessage(
                            role="assistant",
                            content=full_content,
                            reasoning_content=full_reasoning or None,
                        ),
                    )
                usage = chunk.usage or {}
                usage["session_id"] = sid
                finalize_chat_turn(sid, self.name, usage)
                yield self._with_agent(
                    StreamChunk(type="done", content="", usage=usage),
                    a2a_task_id=a2a_task_id,
                )

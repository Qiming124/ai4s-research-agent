# =============================================================================
# Agent 抽象基类与 GeneralAgent 实现。
#
# Phase 2B：GeneralAgent 支持 MCP 工具调用循环。
# =============================================================================

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from server.config import Settings, get_settings
from server.graph.react import build_react_graph, messages_from_api_dicts
from server.graph.streaming import stream_react_graph
from server.langchain.llm import get_chat_model
from server.langchain.tools import mcp_tools_to_langchain
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.llm.prompts import DEFAULT_SYSTEM_PROMPT, MATH_MODE_SYSTEM_PROMPT
from server.memory.base import BaseSessionStore
from server.memory.manager import MemoryManager, get_memory_manager
from server.memory.session import SessionStore, get_session_store
from server.memory.rag.retrieval import build_rag_augmented_prompt
from server.mcp.client import MCPClient, get_mcp_client
from server.mcp.truncation import truncate_tool_result
from server.observability import finalize_chat_turn, set_agent_name, set_session_id
from shared.schemas import ChatMessage, PersistedToolCall, StreamChunk

logger = logging.getLogger(__name__)

_TOOLS_SYSTEM_HINT = (
    "你可以使用提供的工具搜索网络、检索 arXiv 论文或读写实验日志文件。"
    "当用户需要网络搜索、最新资料、论文或 SAM 等术语解释时，**必须**调用 web_search 或 arxiv 工具获取结果，"
    "不要仅凭对话历史断言「搜索不可用」或「请求超时」；每次新的搜索请求都应重新调用工具。"
)


class BaseAgent(ABC):
    name: str = "base"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    @abstractmethod
    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        ...


class GeneralAgent(BaseAgent):
    name = "general"

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: DeepSeekClient | None = None,
        session_store: SessionStore | None = None,
        memory_manager: MemoryManager | None = None,
        mcp_client: MCPClient | None = None,
        *,
        math_mode: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm_client or get_deepseek_client()
        self._sessions: BaseSessionStore = session_store or get_session_store()
        self._memory = memory_manager or get_memory_manager()
        self._mcp = mcp_client
        self.system_prompt = MATH_MODE_SYSTEM_PROMPT if math_mode else self._settings.default_system_prompt

    def _with_agent(self, chunk: StreamChunk) -> StreamChunk:
        return chunk.model_copy(update={"agent_name": self.name})

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

    async def _run_tool_loop(
        self,
        api_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        mcp: MCPClient,
        tool_call_records: list[PersistedToolCall],
    ) -> AsyncIterator[StreamChunk]:
        """
        Legacy 工具调用循环（自研，非 LangGraph）。

        流程：
            1. 发非流式 function-calling 请求（关闭 thinking 以节省 token）
            2. 若 LLM 返回 tool_calls，调用 MCP 执行工具后回填 tool 消息
            3. 循环直到 LLM 不返回 tool_calls 或达到 max_tool_rounds 上限
            4. 最后发一次流式请求生成含 reasoning 的最终回答

        参数:
            api_messages: 包含 system、历史、用户消息的 OpenAI 格式列表
            tools: OpenAI 格式的 tools 列表（传给 function calling）
            mcp: MCP 客户端（执行工具调用的实际后端）
            tool_call_records: 持久化记录的收集列表（由调用方最终写入会话）

        产出:
            StreamChunk: tool_call_start / tool_call_result / tool_call_error
                        / reasoning / content / done
        """
        usage: dict[str, Any] | None = None
        max_result_chars = self._settings.mcp_tool_result_max_chars

        # ── 工具循环（多轮 function calling） ──────────────────────
        for _round in range(self._settings.mcp_max_tool_rounds):
            # 第一步：非流式 function-calling（thinking=off 以提升速度）
            result = await self._llm.chat_with_tools(
                api_messages,
                tools,
                enable_thinking=False,
            )
            if result.usage:
                usage = result.usage

            # 第二步：LLM 未请求工具 → 以当前累积回复结束
            if not result.tool_calls:
                if result.content:
                    yield self._with_agent(StreamChunk(type="content", content=result.content))
                    usage = result.usage or usage
                    yield self._with_agent(StreamChunk(type="done", content="", usage=usage))
                    return
                break  # 既无 tool_calls 也无 content，结束循环

            # 第三步：将 assistant 消息（含 tool_calls）追加到对话上下文
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
                    )
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
                        )
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
                        )
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

        # 最终流式回答（含 reasoning）
        full_content = ""
        full_reasoning = ""
        # 最终流式回答（含 reasoning，thinking=enabled）
        async for chunk in self._llm.stream_chat(api_messages):
            if chunk.type == "reasoning":
                full_reasoning += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "content":
                full_content += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "error":
                yield self._with_agent(chunk)
                return
            elif chunk.type == "done":
                if chunk.usage:
                    usage = chunk.usage
                yield self._with_agent(
                    StreamChunk(type="done", content="", usage=usage)
                )
                return

        yield self._with_agent(StreamChunk(type="done", content="", usage=usage))

    async def _run_langgraph_tool_loop(
        self,
        api_messages: list[dict[str, Any]],
        mcp: MCPClient,
        tool_call_records: list[PersistedToolCall],
    ) -> AsyncIterator[StreamChunk]:
        lc_tools = mcp_tools_to_langchain(mcp, agent_name=self.name)
        if not lc_tools:
            async for chunk in self._llm.stream_chat(api_messages):
                yield self._with_agent(chunk)
            return

        tool_model = get_chat_model(
            self._settings,
            enable_thinking=False,
        )
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
            yield self._with_agent(chunk)

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Agent 主入口：处理用户消息并流式产出回复。

        完整链路：
            1. 创建/获取会话 ID，设置可观测上下文
            2. 从 MemoryManager 获取 L2 全量历史 + L1 截断/摘要
            3. 决定是否启用 MCP 工具（enable_mcp 且 enable_tools 未显式关闭）
            4. 组装 API 消息列表（system + history + user + tools hint）
            5. 根据编排后端选择工具循环路径：
               - langgraph → _run_langgraph_tool_loop
               - legacy   → _run_tool_loop（自研）
               - 无工具   → 直发流式请求
            6. 收集 reasoning + content 完整文本
            7. 存储 user+assistant 消息到 L2 会话，记录 token 用量

        参数:
            message: 用户输入
            session_id: 可选会话 ID；None 时自动生成
            system_prompt_override: 覆盖默认 system prompt
            max_history_messages: L1 截断条数；None=用 .env 默认
            enable_history_summary: 是否对截断部分做摘要；None=用 .env 默认
            enable_tools: 是否启用 MCP；None=用 .env 默认

        产出:
            StreamChunk 流（reasoning/content/done/error/tool_call_*）
        """
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
            "Agent[%s] session=%s 全量历史=%d L1上下文=%d tools=%d",
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
            tool_loop = (
                self._run_langgraph_tool_loop
                if use_langgraph
                else self._run_tool_loop
            )
            tool_loop_args = (
                (api_messages, mcp, persisted_tool_calls)
                if use_langgraph
                else (api_messages, tools, mcp, persisted_tool_calls)
            )
            async for chunk in tool_loop(*tool_loop_args):
                if chunk.type == "content":
                    full_content += chunk.content
                    yield chunk
                elif chunk.type == "reasoning":
                    full_reasoning += chunk.content
                    yield chunk
                elif chunk.type == "done":
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
                        StreamChunk(type="done", content="", usage=usage)
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
                yield self._with_agent(chunk)
            elif chunk.type == "content":
                full_content += chunk.content
                yield self._with_agent(chunk)
            elif chunk.type == "error":
                yield self._with_agent(chunk)
                return
            elif chunk.type == "done":
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
                yield self._with_agent(StreamChunk(type="done", content="", usage=usage))

    async def run_sync(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
    ) -> tuple[str, str, str, dict | None]:
        sid = self._sessions.get_or_create(session_id)
        content = ""
        reasoning = ""
        usage: dict | None = None

        async for chunk in self.run(
            message,
            sid,
            system_prompt_override=system_prompt_override,
            max_history_messages=max_history_messages,
            enable_history_summary=enable_history_summary,
            enable_tools=enable_tools,
        ):
            if chunk.type == "reasoning":
                reasoning += chunk.content
            elif chunk.type == "content":
                content += chunk.content
            elif chunk.type == "done":
                usage = chunk.usage

        return sid, content, reasoning or "", usage


_general_agent: GeneralAgent | None = None


def get_general_agent(*, math_mode: bool = False) -> GeneralAgent:
    global _general_agent
    if math_mode:
        return GeneralAgent(math_mode=True)
    if _general_agent is None:
        _general_agent = GeneralAgent(math_mode=False)
    return _general_agent

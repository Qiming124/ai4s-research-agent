# =============================================================================
# 参数化 ReAct 子 Agent：独立 prompt + 工具白名单。
#
# 职责：
#     MultiAgentOrchestrator 意图路由后，按 agent_name 创建 SubAgent 实例，
#     每个实例绑定专属 system_prompt 和工具白名单。
#
# 与 GeneralAgent 的区别：
#     1. SubAgent 不维护全局单例（每次 create 或由 orchestrator 缓存）
#     2. 支持 RAG（build_rag_augmented_prompt 注入 context）
#     3. 支持 A2A task_id（子任务追踪，填入 SSE StreamChunk.a2a_task_id）
#     4. 支持 persist_session 参数控制是否写入 L2 消息（子 Agent 可能不独立存会话）
#
# 工具循环支持双后端：
#     legacy    → _run_legacy_tool_loop（自研 function calling loop）
#     langgraph → _run_langgraph_tool_loop（LangGraph ReAct 子图）
# =============================================================================

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from server.agents.config import AgentName, get_agent_prompt
from server.artifacts.extract import extract_artifacts_from_text
from server.artifacts.store import get_artifact_store
from server.config import Settings, get_settings
from server.graph.react import build_react_graph, messages_from_api_dicts
from server.graph.streaming import stream_react_graph
from server.graph.theory_pipeline import stream_theory_verification
from server.langchain.llm import get_chat_model
from server.langchain.tools import mcp_tools_to_langchain
from server.graph.workflow import (
    cot_step_chunks,
    finalize_workflow_records,
    upsert_workflow_record,
    workflow_step_chunk,
    workflow_step_record,
)
from server.llm.client import DeepSeekClient, get_deepseek_client
from server.llm.cot_prompt import apply_cot_prompt
from server.llm.reasoning_options import ResolvedReasoningOptions, resolve_reasoning_options
from server.llm.thinking_messages import (
    assistant_message_with_tools,
    prepare_messages_for_deepseek,
    resolve_thinking_for_messages,
)
from server.memory.base import BaseSessionStore
from server.memory.manager import MemoryManager, get_memory_manager
from server.memory.rag.context import reset_rag_session_id, set_rag_session_id
from server.memory.rag.retrieval import build_rag_augmented_prompt
from server.memory.structured.extract import try_persist_structured_entries
from server.memory.structured.injection import build_structured_augmented_prompt
from server.memory.structured.store import get_structured_memory_store
from server.memory.session import SessionStore, get_session_store
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
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            # DeepSeek thinking：历史 assistant 若曾带推理，回传时必须带上 reasoning_content；
            # 若该条还带 tool_calls 元数据，也必须带上（可为空字符串）。
            if msg.role == "assistant":
                if msg.reasoning_content:
                    entry["reasoning_content"] = msg.reasoning_content
                elif msg.tool_calls:
                    entry["reasoning_content"] = ""
            messages.append(entry)

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
        reasoning: ResolvedReasoningOptions,
        workflow_records: list[dict],
        a2a_task_id: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        lc_tools = mcp_tools_to_langchain(mcp, agent_name=self.name)
        if not lc_tools:
            async for chunk in self._llm.stream_chat(
                api_messages,
                enable_thinking=reasoning.enable_thinking,
                reasoning_effort=reasoning.reasoning_effort,
            ):
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)
            return

        yield self._with_agent(
            workflow_step_chunk(
                "plan",
                status="running",
                title="分析问题并规划工具调用",
                agent_name=self.name,
                a2a_task_id=a2a_task_id,
            ),
            a2a_task_id=a2a_task_id,
        )
        upsert_workflow_record(
            workflow_records,
            workflow_step_record(
                "plan",
                status="running",
                title="分析问题并规划工具调用",
            ),
        )

        tool_model = get_chat_model(
            self._settings,
            enable_thinking=False,
            reasoning_effort=reasoning.reasoning_effort,
        )
        final_model = get_chat_model(
            self._settings,
            enable_thinking=reasoning.enable_thinking,
            reasoning_effort=reasoning.reasoning_effort,
        )
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
            workflow_records=workflow_records,
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
        reasoning: ResolvedReasoningOptions,
        workflow_records: list[dict],
        a2a_task_id: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        usage: dict[str, Any] | None = None
        max_result_chars = self._settings.mcp_tool_result_max_chars

        yield self._with_agent(
            workflow_step_chunk(
                "plan",
                status="running",
                title="分析问题并规划工具调用",
                agent_name=self.name,
                a2a_task_id=a2a_task_id,
            ),
            a2a_task_id=a2a_task_id,
        )
        upsert_workflow_record(
            workflow_records,
            workflow_step_record(
                "plan",
                status="running",
                title="分析问题并规划工具调用",
            ),
        )

        for _round in range(self._settings.mcp_max_tool_rounds):
            result = await self._llm.chat_with_tools(
                api_messages,
                tools,
                enable_thinking=False,
            )
            if result.usage:
                usage = result.usage

            if not result.tool_calls:
                yield self._with_agent(
                    workflow_step_chunk(
                        "plan",
                        status="done",
                        title="分析问题并规划工具调用",
                        detail="无需调用工具",
                        agent_name=self.name,
                        a2a_task_id=a2a_task_id,
                    ),
                    a2a_task_id=a2a_task_id,
                )
                upsert_workflow_record(
                    workflow_records,
                    workflow_step_record(
                        "plan",
                        status="done",
                        title="分析问题并规划工具调用",
                        detail="无需调用工具",
                    ),
                )
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

            assistant_msg = assistant_message_with_tools(
                content=result.content or "",
                reasoning_content=result.reasoning,
                tool_calls=[
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
            )
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

        yield self._with_agent(
            workflow_step_chunk(
                "plan",
                status="done",
                title="分析问题并规划工具调用",
                detail="工具规划完成",
                agent_name=self.name,
                a2a_task_id=a2a_task_id,
            ),
            a2a_task_id=a2a_task_id,
        )
        upsert_workflow_record(
            workflow_records,
            workflow_step_record(
                "plan",
                status="done",
                title="分析问题并规划工具调用",
                detail="工具规划完成",
            ),
        )
        yield self._with_agent(
            workflow_step_chunk(
                "synthesize",
                status="running",
                title="综合信息并生成回答",
                agent_name=self.name,
                a2a_task_id=a2a_task_id,
            ),
            a2a_task_id=a2a_task_id,
        )
        upsert_workflow_record(
            workflow_records,
            workflow_step_record(
                "synthesize",
                status="running",
                title="综合信息并生成回答",
            ),
        )

        full_content = ""
        full_reasoning = ""
        # 工具轮 thinking=off 时无真实 reasoning；最终合成须关闭 thinking 避免 400
        final_messages = prepare_messages_for_deepseek(api_messages)
        final_thinking = resolve_thinking_for_messages(
            final_messages, reasoning.enable_thinking
        )
        async for chunk in self._llm.stream_chat(
            final_messages,
            enable_thinking=final_thinking,
            reasoning_effort=reasoning.reasoning_effort,
        ):
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
                    workflow_step_chunk(
                        "synthesize",
                        status="done",
                        title="综合信息并生成回答",
                        detail="回答生成完成",
                        agent_name=self.name,
                        a2a_task_id=a2a_task_id,
                    ),
                    a2a_task_id=a2a_task_id,
                )
                upsert_workflow_record(
                    workflow_records,
                    workflow_step_record(
                        "synthesize",
                        status="done",
                        title="综合信息并生成回答",
                        detail="回答生成完成",
                    ),
                )
                yield self._with_agent(
                    StreamChunk(type="done", content="", usage=usage),
                    a2a_task_id=a2a_task_id,
                )
                return

        yield self._with_agent(
            workflow_step_chunk(
                "synthesize",
                status="done",
                title="综合信息并生成回答",
                detail="回答生成完成",
                agent_name=self.name,
                a2a_task_id=a2a_task_id,
            ),
            a2a_task_id=a2a_task_id,
        )
        upsert_workflow_record(
            workflow_records,
            workflow_step_record(
                "synthesize",
                status="done",
                title="综合信息并生成回答",
                detail="回答生成完成",
            ),
        )
        yield self._with_agent(
            StreamChunk(type="done", content="", usage=usage),
            a2a_task_id=a2a_task_id,
        )

    async def _theory_post_process(
        self,
        full_content: str,
        tool_records: list[PersistedToolCall],
        mcp: MCPClient | None,
        session_id: str,
        *,
        a2a_task_id: str | None = None,
        workflow_records: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """SymPy 验证（仅 theory）+ 引理/定理自动持久化（任意 Agent 输出匹配时）。"""
        verification_results: list[dict] = []
        if self.name == "theory" and mcp is not None and mcp.is_connected and full_content.strip():
            async for chunk in stream_theory_verification(
                mcp,
                full_content,
                tool_records,
                agent_name=self.name,
                a2a_task_id=a2a_task_id,
                workflow_records=workflow_records,
                session_id=session_id,
            ):
                if chunk.type == "verification_result":
                    try:
                        verification_results.append(json.loads(chunk.content))
                    except Exception:
                        pass
                elif chunk.type == "numerical_verification_result":
                    try:
                        verification_results.append(json.loads(chunk.content))
                    except Exception:
                        pass
                yield self._with_agent(chunk, a2a_task_id=a2a_task_id)

        if full_content.strip():
            store = get_structured_memory_store()
            saved, warnings = try_persist_structured_entries(
                full_content,
                session_id,
                store,
                verification_results=verification_results if verification_results else None,
                source="theory_auto_extract" if self.name == "theory" else "auto_extract",
            )
            if saved:
                logger.info(
                    "自动持久化 %d 条结构化记忆 agent=%s session=%s",
                    len(saved),
                    self.name,
                    session_id,
                )
            for warning in warnings:
                yield StreamChunk(
                    type="memory_warning",
                    content=warning,
                    agent_name=self.name,
                    a2a_task_id=a2a_task_id,
                )

    async def run(
        self,
        message: str,
        session_id: str | None,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        cot_mode: str = "standard",
        a2a_task_id: str | None = None,
        persist_session: bool = True,
        enable_rag: bool | None = None,
        augment_structured_memory: bool = True,
        project_id: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        SubAgent 主入口：处理用户消息并流式产出回复。

        完整链路（与 GeneralAgent.run 类似，额外支持）：
            1. 若 ENABLE_RAG 且本 Agent 在 rag_agents 中 → 注入 RAG 上下文
            2. A2A task_id 填入每个 StreamChunk（用于前端/日志的跨 Agent 追踪）
            3. persist_session=False 时跳过 L2 会话写入（子 Agent 临时调用场景）

        参数:
            message: 用户输入
            session_id: 可选会话 ID
            system_prompt_override: 覆盖默认 prompt
            max_history_messages: L1 截断条数
            enable_history_summary: 截断时是否摘要
            enable_tools: 是否启用 MCP
            a2a_task_id: A2A 子任务 ID（由 orchestrator 分配）
            persist_session: 是否写入 L2 消息（默认 True）
            enable_rag: 是否注入 RAG（None=跟随全局配置）
            augment_structured_memory: 是否注入 L4 结构化记忆（收尾可关）
            project_id: 课题 ID（用于 Artifact 落盘）

        产出:
            StreamChunk 流
        """
        sid = self._sessions.get_or_create(session_id)
        set_session_id(sid)
        set_agent_name(self.name)
        rag_token = set_rag_session_id(sid)
        try:
            async for chunk in self._run_impl(
                sid,
                message,
                system_prompt_override=system_prompt_override,
                max_history_messages=max_history_messages,
                enable_history_summary=enable_history_summary,
                enable_tools=enable_tools,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
                cot_mode=cot_mode,
                a2a_task_id=a2a_task_id,
                persist_session=persist_session,
                enable_rag=enable_rag,
                augment_structured_memory=augment_structured_memory,
                project_id=project_id or "default",
            ):
                yield chunk
        finally:
            reset_rag_session_id(rag_token)

    async def _run_impl(
        self,
        sid: str,
        message: str,
        *,
        system_prompt_override: str | None = None,
        max_history_messages: int | None = None,
        enable_history_summary: bool | None = None,
        enable_tools: bool | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        cot_mode: str = "standard",
        a2a_task_id: str | None = None,
        persist_session: bool = True,
        enable_rag: bool | None = None,
        augment_structured_memory: bool = True,
        project_id: str = "default",
    ) -> AsyncIterator[StreamChunk]:
        pid = project_id or "default"
        reasoning = resolve_reasoning_options(
            self._settings,
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,  # type: ignore[arg-type]
        )
        system_prompt = system_prompt_override or self.system_prompt
        system_prompt = apply_cot_prompt(system_prompt, cot_mode, self.name)  # type: ignore[arg-type]

        rag_on = (
            self._settings.enable_rag if enable_rag is None else enable_rag
        )
        if rag_on and self.name in self._settings.rag_agent_names():
            system_prompt = build_rag_augmented_prompt(
                system_prompt,
                message,
                sid,
                self._settings,
            )

        if augment_structured_memory:
            system_prompt = build_structured_augmented_prompt(
                system_prompt,
                sid,
                self.name,
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
        workflow_records: list[dict] = []

        if effective_tools and mcp is not None:
            use_langgraph = self._settings.orchestration_backend == "langgraph"
            if use_langgraph:
                tool_iter = self._run_langgraph_tool_loop(
                    api_messages,
                    mcp,
                    persisted_tool_calls,
                    reasoning=reasoning,
                    workflow_records=workflow_records,
                    a2a_task_id=a2a_task_id,
                )
            else:
                tool_iter = self._run_legacy_tool_loop(
                    api_messages,
                    tools,
                    mcp,
                    persisted_tool_calls,
                    reasoning=reasoning,
                    workflow_records=workflow_records,
                    a2a_task_id=a2a_task_id,
                )

            async for chunk in tool_iter:
                if chunk.type == "content":
                    full_content += chunk.content
                    yield chunk
                elif chunk.type == "reasoning":
                    full_reasoning += chunk.content
                    yield chunk
                elif chunk.type == "done":
                    for cot_chunk in cot_step_chunks(full_content, agent_name=self.name):
                        yield self._with_agent(cot_chunk, a2a_task_id=a2a_task_id)
                    async for post_chunk in self._theory_post_process(
                        full_content,
                        persisted_tool_calls,
                        mcp,
                        sid,
                        a2a_task_id=a2a_task_id,
                        workflow_records=workflow_records,
                    ):
                        yield post_chunk
                    if self._settings.enable_artifact_store and full_content.strip():
                        for atype, payload in extract_artifacts_from_text(full_content):
                            payload.setdefault("project_id", pid)
                            payload.setdefault("session_id", sid)
                            try:
                                saved = get_artifact_store().save(atype, payload)
                            except Exception as exc:
                                logger.warning("artifact 落盘失败 type=%s: %s", atype, exc)
                                yield self._with_agent(
                                    StreamChunk(
                                        type="error",
                                        content=f"工件 {atype} 保存失败（已跳过）：{exc}",
                                    ),
                                    a2a_task_id=a2a_task_id,
                                )
                                continue
                            yield self._with_agent(
                                StreamChunk(
                                    type="artifact_saved",
                                    content=json.dumps(
                                        {
                                            "type": atype,
                                            "id": saved["id"],
                                            "title": saved.get("title") or saved["id"],
                                        },
                                        ensure_ascii=False,
                                    ),
                                    title=str(saved.get("title") or saved["id"]),
                                ),
                                a2a_task_id=a2a_task_id,
                            )
                    if persist_session:
                        self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                        self._sessions.append_message(
                            sid,
                            ChatMessage(
                                role="assistant",
                                content=full_content,
                                reasoning_content=full_reasoning or None,
                                tool_calls=persisted_tool_calls or None,
                                workflow_steps=finalize_workflow_records(workflow_records),
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

        async for chunk in self._llm.stream_chat(
            api_messages,
            enable_thinking=reasoning.enable_thinking,
            reasoning_effort=reasoning.reasoning_effort,
        ):
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
                for cot_chunk in cot_step_chunks(full_content, agent_name=self.name):
                    yield self._with_agent(cot_chunk, a2a_task_id=a2a_task_id)
                async for post_chunk in self._theory_post_process(
                    full_content,
                    [],
                    mcp,
                    sid,
                    a2a_task_id=a2a_task_id,
                    workflow_records=workflow_records,
                ):
                    yield post_chunk
                if self._settings.enable_artifact_store and full_content.strip():
                    for atype, payload in extract_artifacts_from_text(full_content):
                        payload.setdefault("project_id", pid)
                        payload.setdefault("session_id", sid)
                        try:
                            saved = get_artifact_store().save(atype, payload)
                        except Exception as exc:
                            logger.warning("artifact 落盘失败 type=%s: %s", atype, exc)
                            yield self._with_agent(
                                StreamChunk(
                                    type="error",
                                    content=f"工件 {atype} 保存失败（已跳过）：{exc}",
                                ),
                                a2a_task_id=a2a_task_id,
                            )
                            continue
                        yield self._with_agent(
                            StreamChunk(
                                type="artifact_saved",
                                content=json.dumps(
                                    {
                                        "type": atype,
                                        "id": saved["id"],
                                        "title": saved.get("title") or saved["id"],
                                    },
                                    ensure_ascii=False,
                                ),
                                title=str(saved.get("title") or saved["id"]),
                            ),
                            a2a_task_id=a2a_task_id,
                        )
                if persist_session:
                    self._sessions.append_message(sid, ChatMessage(role="user", content=message))
                    self._sessions.append_message(
                        sid,
                        ChatMessage(
                            role="assistant",
                            content=full_content,
                            reasoning_content=full_reasoning or None,
                            workflow_steps=finalize_workflow_records(workflow_records),
                        ),
                    )
                usage = chunk.usage or {}
                usage["session_id"] = sid
                finalize_chat_turn(sid, self.name, usage)
                yield self._with_agent(
                    StreamChunk(type="done", content="", usage=usage),
                    a2a_task_id=a2a_task_id,
                )

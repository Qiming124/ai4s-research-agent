# =============================================================================
# server.graph 包：LangGraph 工作流与科研流水线。
#
# 职责：
#     1. react.py / streaming.py — ReAct 工具循环子图
#     2. scenes/ — 场景工作流
#     3. theory_pipeline.py / workflow.py — 推导验证与工作流 SSE
#     4. router_llm.py — LLM 意图路由
#
# 架构位置：
#     - 被调用：server/agents/orchestrator.py、base.py、subagent.py
#     - 调用：server/agents/subagent.py、server/mcp/client.py、server/memory/
#
# 阅读提示：
#     - 新人先看 build_react_graph（react.py）与 ResearchSupervisorPipeline.execute
#
# Debug：
#     - 子图不终止 → tool 循环无 final answer，查 max_iterations
# =============================================================================

from server.graph.react import build_react_graph, messages_from_api_dicts
from server.graph.streaming import stream_react_graph

__all__ = [
    "build_react_graph",
    "messages_from_api_dicts",
    "stream_react_graph",
]

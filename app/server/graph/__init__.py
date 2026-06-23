"""LangGraph ReAct tool loop (Phase 3).

导出：
    build_react_graph     — 编译 ReAct 子图（call_model ↔ execute_tools）
    messages_from_api_dicts — OpenAI dict → LangChain BaseMessage 转换
    stream_react_graph      — 运行子图 + 流式生成最终回答 → SSE StreamChunk
"""

from server.graph.react import build_react_graph, messages_from_api_dicts
from server.graph.streaming import stream_react_graph

__all__ = [
    "build_react_graph",
    "messages_from_api_dicts",
    "stream_react_graph",
]

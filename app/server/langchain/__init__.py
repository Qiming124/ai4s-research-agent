"""LangChain / LangGraph adapter layer (Phase 3).

为 LangGraph ReAct 工具循环提供：
    - get_chat_model()         → DeepSeek via ChatOpenAI 实例
    - mcp_tools_to_langchain()  → MCPClient → StructuredTool 列表

渐进迁移策略：
    生产路径默认 legacy（server/llm/client.py），
    当 ORCHESTRATION_BACKEND=langgraph 时启用本层。
"""

from server.langchain.llm import build_chat_model_kwargs, get_chat_model
from server.langchain.mcp import build_multiserver_connections, create_multiserver_client

__all__ = [
    "build_chat_model_kwargs",
    "build_multiserver_connections",
    "create_multiserver_client",
    "get_chat_model",
]

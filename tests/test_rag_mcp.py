"""RAG MCP Server 单元测试。"""

import json

import pytest

from server.mcp.servers import rag as rag_server


@pytest.mark.asyncio
async def test_rag_retrieve_disabled():
    result = await rag_server.retrieve("theta 符号", top_k=2)
    data = json.loads(result)
    assert "error" in data or "results" in data

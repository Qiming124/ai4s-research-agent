"""RAG MCP Server 单元测试。"""

import json
import tempfile
from pathlib import Path

import pytest

from server.config import Settings, get_settings
from server.mcp.servers import rag as rag_server


@pytest.mark.asyncio
async def test_rag_retrieve_disabled(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        deepseek_api_key="sk-test",
        enable_rag=False,
    )
    monkeypatch.setattr("server.config.get_settings", lambda: settings)

    result = await rag_server.retrieve("theta 符号", top_k=2, session_id="sess-test")
    data = json.loads(result)
    assert "error" in data
    assert "RAG 未启用" in data["error"]


@pytest.mark.asyncio
async def test_rag_retrieve_requires_session_when_enabled(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            deepseek_api_key="sk-test",
            rag_embedding_provider="test",
            rag_chroma_path=str(Path(tmp) / "chroma"),
            enable_rag=True,
        )
        monkeypatch.setattr("server.config.get_settings", lambda: settings)

        result = await rag_server.retrieve("query", top_k=2, session_id="")
        data = json.loads(result)
        assert "error" in data
        assert "session_id" in data["error"]

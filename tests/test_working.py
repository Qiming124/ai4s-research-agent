"""
L1 Working Memory 单元测试。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from server.memory.working import prepare_history_for_llm
from shared.schemas import ChatMessage


def _history(n: int) -> list[ChatMessage]:
    msgs: list[ChatMessage] = []
    for i in range(n):
        msgs.append(ChatMessage(role="user", content=f"q{i}"))
        msgs.append(ChatMessage(role="assistant", content=f"a{i}"))
    return msgs


@pytest.mark.asyncio
async def test_prepare_history_no_trim() -> None:
    history = _history(3)
    result = await prepare_history_for_llm(
        history,
        max_messages=0,
        enable_summary=False,
        llm=AsyncMock(),
        summary_max_tokens=1024,
    )
    assert result == history


@pytest.mark.asyncio
async def test_prepare_history_tail_trim() -> None:
    history = _history(5)
    result = await prepare_history_for_llm(
        history,
        max_messages=4,
        enable_summary=False,
        llm=AsyncMock(),
        summary_max_tokens=1024,
    )
    assert len(result) == 4
    assert result[-1].content == "a4"


@pytest.mark.asyncio
async def test_prepare_history_with_summary() -> None:
    history = _history(5)
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value=("摘要内容", None, None))

    result = await prepare_history_for_llm(
        history,
        max_messages=4,
        enable_summary=True,
        llm=llm,
        summary_max_tokens=512,
    )

    assert len(result) == 5
    assert result[0].role == "system"
    assert "摘要内容" in result[0].content
    assert result[-1].content == "a4"
    llm.chat.assert_awaited_once()

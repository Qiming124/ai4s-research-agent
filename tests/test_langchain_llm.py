"""
LangChain LLM 工厂单元测试。

运行：pytest tests/test_langchain_llm.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.config import Settings, get_settings
from server.langchain.llm import build_chat_model_kwargs, get_chat_model
from server.llm.client import DeepSeekClient


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test-key-for-pytest-only",
        deepseek_base_url="https://api.deepseek.com",
        model="deepseek-v4-pro",
        max_tokens=8192,
        reasoning_effort="max",
    )


def test_build_chat_model_kwargs_matches_deepseek_client(test_settings: Settings) -> None:
    """LangChain 工厂参数与 DeepSeekClient._build_create_kwargs 核心字段一致。"""
    lc_kwargs = build_chat_model_kwargs(test_settings)
    ds_kwargs = DeepSeekClient(test_settings)._build_create_kwargs(
        [{"role": "user", "content": "hi"}],
        stream=False,
    )

    assert lc_kwargs["model"] == ds_kwargs["model"]
    assert lc_kwargs["max_tokens"] == ds_kwargs["max_tokens"]
    assert lc_kwargs["reasoning_effort"] == ds_kwargs["reasoning_effort"]
    assert lc_kwargs["extra_body"] == ds_kwargs["extra_body"]


def test_get_chat_model_uses_settings(test_settings: Settings) -> None:
    model = get_chat_model(test_settings)
    assert model.model_name == test_settings.model
    assert model.max_tokens == test_settings.max_tokens
    assert model.openai_api_base.rstrip("/") == test_settings.deepseek_base_url.rstrip("/")
    assert model.reasoning_effort == test_settings.reasoning_effort


def test_get_chat_model_disable_thinking(test_settings: Settings) -> None:
    kwargs = build_chat_model_kwargs(test_settings, enable_thinking=False)
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_validate_orchestration_backend() -> None:
    with pytest.raises(ValueError, match="ORCHESTRATION_BACKEND"):
        Settings(
            deepseek_api_key="sk-test-key",
            orchestration_backend="invalid",
        )


def test_orchestration_backend_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")
    monkeypatch.delenv("ORCHESTRATION_BACKEND", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().orchestration_backend == "legacy"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_chat_model_invoke_mock(test_settings: Settings) -> None:
    """可选 invoke：mock ChatOpenAI.ainvoke 验证工厂可调用。"""
    mock_response = MagicMock()
    mock_response.content = "hello from mock"

    with patch.object(
        type(get_chat_model(test_settings)),
        "ainvoke",
        new=AsyncMock(return_value=mock_response),
    ) as mock_ainvoke:
        model = get_chat_model(test_settings)
        result = await model.ainvoke("ping")
        assert result.content == "hello from mock"
        mock_ainvoke.assert_awaited_once()

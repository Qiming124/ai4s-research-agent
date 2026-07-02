"""ChatRequest 推理参数解析与透传。"""

from server.llm.reasoning_options import resolve_reasoning_options
from server.config import Settings
from shared.schemas import ChatRequest


def test_chat_request_reasoning_fields_optional():
    req = ChatRequest(message="hello")
    assert req.enable_thinking is None
    assert req.reasoning_effort is None
    assert req.cot_mode == "standard"


def test_resolve_reasoning_defaults():
    settings = Settings(deepseek_api_key="sk-test", reasoning_effort="max")
    opts = resolve_reasoning_options(settings)
    assert opts.enable_thinking is True
    assert opts.reasoning_effort == "max"


def test_resolve_reasoning_override():
    settings = Settings(deepseek_api_key="sk-test", reasoning_effort="max")
    opts = resolve_reasoning_options(
        settings,
        enable_thinking=False,
        reasoning_effort="high",
    )
    assert opts.enable_thinking is False
    assert opts.reasoning_effort == "high"

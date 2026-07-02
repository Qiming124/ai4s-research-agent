# 请求级推理参数解析（enable_thinking / reasoning_effort）。

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from server.config import Settings

ReasoningEffort = Literal["high", "max"]


@dataclass(frozen=True)
class ResolvedReasoningOptions:
    """解析后的推理选项（用于最终回答流式生成）。"""

    enable_thinking: bool
    reasoning_effort: str


def resolve_reasoning_options(
    settings: Settings,
    *,
    enable_thinking: bool | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> ResolvedReasoningOptions:
    """
    将 ChatRequest 可选字段解析为实际 LLM 参数。

    enable_thinking=None 时默认 True（与历史行为一致：最终回答启用 thinking）。
    reasoning_effort=None 时使用服务端 .env 默认值。
    """
    return ResolvedReasoningOptions(
        enable_thinking=True if enable_thinking is None else enable_thinking,
        reasoning_effort=reasoning_effort or settings.reasoning_effort,
    )

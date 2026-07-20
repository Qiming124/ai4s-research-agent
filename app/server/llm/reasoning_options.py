# =============================================================================
# 请求级推理参数解析（enable_thinking / reasoning_effort）。
#
# 职责：
#     1. ResolvedReasoningOptions 数据类封装最终推理开关
#     2. resolve_reasoning_options() 合并 Settings 默认值与请求级覆盖
#     3. 供 GeneralAgent / SubAgent 流式调用 DeepSeek reasoning 模型
#
# 架构位置：
#     - 被调用：server/agents/base.py、subagent.py、llm/client.py
#     - 调用：server/config.Settings
#
# 阅读提示：
#     - 新人先看 resolve_reasoning_options
#
# Debug：
#     - 无 reasoning 输出 → enable_thinking=false 或 reasoning_effort 过低
# =============================================================================

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

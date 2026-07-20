# =============================================================================
# L1 Working Memory：历史截断与可选 LLM 摘要。
#
# 职责：在调用 LLM 前，将 L2 完整会话历史处理为适合 context 窗口的消息列表。
#       L2 数据库仍保留完整记录，此处只做读取侧变换。
#
# 策略：
#     1. max_messages < 0 → 空历史（收尾等轻量场景）
#     2. max_messages == 0 → 不截断
#     3. len(history) <= max_messages → 不截断
#     4. 否则保留最近 max_messages 条；丢弃部分可选 LLM 摘要（enable_summary）
# =============================================================================

from __future__ import annotations

import logging

from server.llm.client import DeepSeekClient
from shared.schemas import ChatMessage

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "请将以下对话历史压缩为简洁中文摘要，保留关键问题、结论与未决事项。不超过 500 字。"
)


def _format_history_text(messages: list[ChatMessage]) -> str:
    lines: list[str] = []
    for msg in messages:
        label = {"user": "用户", "assistant": "助手", "system": "系统"}.get(msg.role, msg.role)
        lines.append(f"{label}: {msg.content}")
    return "\n".join(lines)


async def _summarize_dropped_messages(
    dropped: list[ChatMessage],
    *,
    llm: DeepSeekClient,
    summary_max_tokens: int,
) -> str:
    if not dropped:
        return ""
    history_text = _format_history_text(dropped)
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": history_text},
    ]
    content, _, _ = await llm.chat(
        messages,
        reasoning_effort="high",
        max_tokens=summary_max_tokens,
        enable_thinking=False,
    )
    return content.strip()


async def prepare_history_for_llm(
    history: list[ChatMessage],
    *,
    max_messages: int,
    enable_summary: bool,
    llm: DeepSeekClient,
    summary_max_tokens: int,
) -> list[ChatMessage]:
    # 将 L2 完整历史处理为注入 LLM 的上下文列表。
    #
    # 参数 max_messages — 保留最近 N 条；0 表示不截断；负数表示空历史。
    # 参数 enable_summary — 截断时是否对丢弃部分做 LLM 摘要。
    # 返回处理后的 ChatMessage 列表（可能含一条 system 摘要消息 + kept）。
    if max_messages < 0:
        return []
    if max_messages == 0 or len(history) <= max_messages:
        return list(history)

    dropped = history[:-max_messages]
    kept = history[-max_messages:]

    if not enable_summary:
        return kept

    try:
        summary = await _summarize_dropped_messages(
            dropped,
            llm=llm,
            summary_max_tokens=summary_max_tokens,
        )
    except Exception:
        logger.exception("历史摘要失败，回退为仅保留最近 %d 条", max_messages)
        return kept

    if not summary:
        return kept

    summary_msg = ChatMessage(
        role="system",
        content=f"【此前对话摘要】\n{summary}",
    )
    return [summary_msg, *kept]

# =============================================================================
# DeepSeek thinking / tool_calls 消息兼容。
#
# 规则（官方文档）：
#   1. 若某轮 assistant 含 tool_calls，其 reasoning_content 必须在后续请求中原样回传，
#      否则 API 返回 400：reasoning_content must be passed back。
#   2. assistant.tool_calls 之后必须紧跟对应 tool_call_id 的 tool 消息，
#      否则 API 返回 400：insufficient tool messages following tool_calls message。
#   3. 本项目工具轮常关闭 thinking，最终回答再开启 → 空串占位不足以绕过校验；
#      含 tool_calls 历史时最终合成须强制关闭 thinking。
#
# 典型根因（规则 2）：
#   LangGraph 在 tool_rounds 达上限后仍 call_model，若再返回 tool_calls 则直接 END，
#   未执行 execute_tools，最终合成带着「悬空 tool_calls」请求 DeepSeek → 400。
# =============================================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MISSING_TOOL_PLACEHOLDER = (
    "[系统] 该 tool_call 缺少执行结果（可能因工具轮次上限或中断），已自动补全占位。"
)


def has_assistant_tool_calls(messages: list[dict[str, Any]]) -> bool:
    """消息列表中是否存在带 tool_calls 的 assistant 消息。"""
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            return True
    return False


def resolve_thinking_for_messages(
    messages: list[dict[str, Any]],
    requested: bool,
) -> bool:
    """
    根据消息历史决定最终请求是否启用 thinking。

    含 tool_calls 的 assistant 历史时强制关闭（工具轮未产生可回传的
    reasoning_content，开启 thinking 会 400）；否则尊重 requested。
    """
    if has_assistant_tool_calls(messages):
        return False
    return requested


def ensure_reasoning_content_for_tool_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    保证含 tool_calls 的 assistant 消息带有 reasoning_content 键。

    已有非空值则保留；缺失或 None 时写入空字符串（工具轮 thinking=off 时的占位）。
    注意：空串 alone 不能在 thinking=on 时绕过 DeepSeek 校验，须配合
    resolve_thinking_for_messages 关闭 thinking。
    不修改原列表，返回新列表。
    """
    out: list[dict[str, Any]] = []
    for raw in messages:
        msg = dict(raw)
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            if msg.get("reasoning_content") is None:
                msg["reasoning_content"] = ""
        out.append(msg)
    return out


def sanitize_tool_call_pairing(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    保证每条含 tool_calls 的 assistant 后都有齐全的 tool 回复。

    - 缺失的 tool_call_id → 插入占位 tool 消息（避免 DeepSeek 400）
    - 紧随其后的多余 / 孤儿 tool 消息 → 丢弃
    - 不修改入参列表，返回新列表
    """
    out: list[dict[str, Any]] = []
    i = 0
    n = len(messages)
    patched = 0

    while i < n:
        raw = messages[i]
        msg = dict(raw)
        role = msg.get("role")

        if role == "assistant" and msg.get("tool_calls"):
            tool_calls = msg.get("tool_calls") or []
            expected_ids: list[str] = []
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                tid = tc.get("id")
                if isinstance(tid, str) and tid:
                    expected_ids.append(tid)

            if msg.get("reasoning_content") is None:
                msg["reasoning_content"] = ""
            out.append(msg)

            j = i + 1
            found: dict[str, dict[str, Any]] = {}
            while j < n and messages[j].get("role") == "tool":
                tid = messages[j].get("tool_call_id")
                if isinstance(tid, str) and tid and tid not in found:
                    found[tid] = dict(messages[j])
                j += 1

            for tid in expected_ids:
                if tid in found:
                    out.append(found[tid])
                else:
                    patched += 1
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": tid,
                            "content": _MISSING_TOOL_PLACEHOLDER,
                        }
                    )
            i = j
            continue

        if role == "tool":
            # 没有前置 assistant.tool_calls 的孤儿 tool → 丢弃
            patched += 1
            i += 1
            continue

        out.append(msg)
        i += 1

    if patched:
        logger.warning(
            "sanitize_tool_call_pairing: 修补/丢弃 %d 处不完整 tool 配对（避免 DeepSeek 400）",
            patched,
        )
    return out


def prepare_messages_for_deepseek(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """出站前统一处理：补齐 tool 配对 + reasoning_content 占位。"""
    paired = sanitize_tool_call_pairing(messages)
    return ensure_reasoning_content_for_tool_messages(paired)


def assistant_message_with_tools(
    *,
    content: str | None,
    tool_calls: list[dict[str, Any]],
    reasoning_content: str | None = None,
) -> dict[str, Any]:
    """构造可回传给 DeepSeek 的 assistant + tool_calls 消息。"""
    return {
        "role": "assistant",
        "content": content or "",
        "reasoning_content": reasoning_content if reasoning_content is not None else "",
        "tool_calls": tool_calls,
    }

# =============================================================================
# 工具返回结果截断：写入 LLM 上下文前按字符上限裁剪。
#
# 职责：
#     防止工具返回结果过长挤压 LLM 上下文窗口。
#     当结果超过 max_chars 时，保留前 max_chars 字符，并在末尾附加省略提示。
#
# 使用场景：
#     - GeneralAgent._run_tool_loop  → 每个 tool_call_result 后截断
#     - SubAgent._run_legacy_tool_loop → 同上
#     - graph/nodes.py execute_tools   → 同上（LangGraph 路径）
#
# max_chars 来源：conf/.env MCP_TOOL_RESULT_MAX_CHARS（默认 8000）
# =============================================================================

from __future__ import annotations


def truncate_tool_result(content: str, max_chars: int) -> str:
    """
    按字符数截断工具返回内容。

    参数:
        content: 工具返回的原始文本
        max_chars: 保留的最大字符数；<=0 时不截断

    返回:
        截断后的内容（含省略提示）或原始内容（未超过上限）

    省略提示格式：
        "... 工具结果已截断：省略 N 字符，原文共 M 字符"
    """
    if max_chars <= 0:
        return content  # 不截断
    if len(content) <= max_chars:
        return content  # 未超过上限

    omitted = len(content) - max_chars
    return (
        f"{content[:max_chars]}\n\n"
        f"[... 工具结果已截断：省略 {omitted} 字符，原文共 {len(content)} 字符]"
    )

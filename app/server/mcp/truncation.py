# 工具返回结果截断：写入 LLM 上下文前按字符上限裁剪。

from __future__ import annotations


def truncate_tool_result(content: str, max_chars: int) -> str:
    if max_chars <= 0:
        return content
    if len(content) <= max_chars:
        return content
    omitted = len(content) - max_chars
    return (
        f"{content[:max_chars]}\n\n"
        f"[... 工具结果已截断：省略 {omitted} 字符，原文共 {len(content)} 字符]"
    )

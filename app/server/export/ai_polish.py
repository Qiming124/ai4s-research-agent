# 导出前 AI 润色：根据用户要求改写 Markdown 草稿。

from __future__ import annotations

import logging
import re

from server.llm.client import get_deepseek_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是学术论文编辑助手。用户会提供 Markdown 论文草稿与润色要求。
请输出修订后的完整 Markdown，遵守：
1. 保留一级标题 # 与二级标题 ## 的分节结构（定理/引理/笔记等标签可保留）
2. 不捏造草稿中未出现的定理、数据或实验结论
3. 使用中文撰写，公式用 $...$ 或 $$...$$
4. 只输出 Markdown 正文，不要 ``` 围栏，不要附加解释"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$", text, flags=re.I)
    if m:
        return m.group(1).strip()
    return text


def _looks_like_markdown(text: str) -> bool:
    return bool(text.strip()) and ("#" in text or "##" in text or len(text) > 80)


async def polish_export_markdown(
    *,
    title: str,
    markdown: str,
    instructions: str,
) -> tuple[str, bool]:
    """按用户要求调用 LLM 润色导出 Markdown。返回 (结果, 是否已应用 AI)。"""
    instructions = (instructions or "").strip()
    if not instructions:
        return markdown, False

    user_prompt = (
        f"论文标题：{title or '研究报告'}\n\n"
        f"润色要求：\n{instructions}\n\n"
        f"草稿 Markdown：\n{markdown}"
    )

    try:
        client = get_deepseek_client()
        content, _, _ = await client.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            reasoning_effort="high",
            enable_thinking=False,
            max_tokens=8192,
        )
        polished = _strip_code_fence((content or "").strip())
        if _looks_like_markdown(polished):
            return polished, True
        logger.warning("AI 润色输出不像 Markdown，回退原稿")
    except Exception as exc:
        logger.warning("导出 AI 润色失败，回退原稿: %s", exc)

    return markdown, False

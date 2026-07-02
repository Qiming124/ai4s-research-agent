# 结构化思维链（CoT）提示词注入。

from __future__ import annotations

from typing import Literal

CotMode = Literal["off", "standard", "strict"]

STRUCTURED_COT_SUFFIX_STANDARD = """## 回答结构（思维链）
请按以下 Markdown 小节顺序组织**最终回答**（每节必须有实质内容）：
1. `## 问题分析` — 重述问题、列出关键假设与已知条件
2. `## 推理过程` — 分步推导或论证，标明每步依据
3. `## 结论` — 简明总结可执行的结论或建议"""

STRUCTURED_COT_SUFFIX_STRICT = """## 回答结构（严格思维链）
**必须**使用且仅使用以下三个 Markdown 二级标题作为最终回答的结构（顺序不可变、标题不可改）：
## 问题分析
（本节内容）

## 推理过程
（本节内容）

## 结论
（本节内容）

禁止省略任一小节；不确定处标注「待验证」。"""


def apply_cot_prompt(
    base_prompt: str,
    cot_mode: CotMode,
    agent_name: str,
) -> str:
    """按 cot_mode 为 system prompt 注入结构化思维链后缀。Theory Agent 已有分阶段 CoT，不重复注入。"""
    if cot_mode == "off":
        return base_prompt
    if agent_name == "theory":
        return base_prompt
    suffix = (
        STRUCTURED_COT_SUFFIX_STRICT
        if cot_mode == "strict"
        else STRUCTURED_COT_SUFFIX_STANDARD
    )
    return f"{base_prompt}\n\n{suffix}"

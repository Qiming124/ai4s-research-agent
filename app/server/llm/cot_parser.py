# =============================================================================
# 从模型回答正文解析结构化思维链（CoT）小节。
#
# 职责：
#     1. parse_cot_sections() 按 Markdown ## 标题切分步骤
#     2. CotStep 数据类承载 step / title / body
#     3. 供 workflow SSE 与前端 CoT 面板展示
#
# 架构位置：
#     - 被调用：server/agents/base.py、subagent.py（cot_mode 相关）
#     - 调用：无
#
# 阅读提示：
#     - 新人先看 parse_cot_sections 与 _SECTION_RE
#
# Debug：
#     - 步骤为空 → 模型输出无 ## 二级标题
#     - 步骤合并错乱 → 正文含未转义的 ## 行
# =============================================================================

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CotStep:
    step: int
    title: str
    body: str


_SECTION_RE = re.compile(
    r"^##\s+(.+?)\s*$",
    re.MULTILINE,
)


def parse_cot_sections(content: str) -> list[CotStep]:
    """
    按 Markdown `## 标题` 切分正文为思维链步骤。

    返回按出现顺序编号的 CotStep 列表；无二级标题时返回空列表。
    """
    text = content.strip()
    if not text:
        return []

    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return []

    steps: list[CotStep] = []
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            steps.append(CotStep(step=idx + 1, title=title, body=body))
    return steps

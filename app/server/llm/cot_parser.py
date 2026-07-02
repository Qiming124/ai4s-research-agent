# 从模型回答正文中解析结构化思维链小节。

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

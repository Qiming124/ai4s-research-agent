# 意图分类：规则路由到 theory / experiment / literature / general。

from __future__ import annotations

import re

from server.agents.config import AgentName

_THEORY_PATTERNS = [
    r"\bderive\b",
    r"\bprove\b",
    r"\btheorem\b",
    r"\bconvergence\b",
    r"\bgradient\b",
    r"推导",
    r"证明",
    r"定理",
    r"损失函数",
    r"优化理论",
    r"收敛",
    r"不等式",
]

_EXPERIMENT_PATTERNS = [
    r"\bexperiment\b",
    r"\blog\b",
    r"\bmetric\b",
    r"\btraining\b",
    r"实验",
    r"日志",
    r"指标",
    r"训练曲线",
    r"过拟合",
    r"loss\s*曲线",
    r"read_file",
    r"实验日志",
]

_LITERATURE_PATTERNS = [
    r"\barxiv\b",
    r"\bpaper\b",
    r"\bliterature\b",
    r"\bcite\b",
    r"文献",
    r"论文",
    r"综述",
    r"检索",
    r"引用",
    r"related work",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def classify_intent(
    message: str,
    *,
    mode: str = "chat",
) -> tuple[AgentName, str]:
    """规则分类用户意图，返回 (agent_name, route_reason)。"""
    if mode == "math":
        return "theory", "mode=math"

    text = message.strip()
    if not text:
        return "general", "empty_message"

    if _matches_any(text, _LITERATURE_PATTERNS):
        return "literature", "keyword:literature"

    if _matches_any(text, _EXPERIMENT_PATTERNS):
        return "experiment", "keyword:experiment"

    if _matches_any(text, _THEORY_PATTERNS):
        return "theory", "keyword:theory"

    return "general", "default"

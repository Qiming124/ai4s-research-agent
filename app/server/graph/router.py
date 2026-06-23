# =============================================================================
# 意图分类：基于正则匹配的规则路由。
#
# 职责：根据用户消息中的关键词，决定应路由到哪个子 Agent。
#       这是 Phase 3 的轻量路由方案（替代 LLM 分类器）。
#
# 分类优先级（从高到低）：
#     1. 显式 mode=math → theory
#     2. 文献相关关键词 → literature
#     3. 实验相关关键词 → experiment
#     4. 理论相关关键词 → theory
#     5. 未命中 → general
#
# 架构位置：
#     server/agents/orchestrator.py → MultiAgentOrchestrator.resolve_target_agent
# =============================================================================

from __future__ import annotations

import re

from server.agents.config import AgentName

# ── 理论推导关键词（中英文） ─────────────────────────────────
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

# ── 实验分析关键词 ───────────────────────────────────────────
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

# ── 文献检索关键词 ───────────────────────────────────────────
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
    """大小写不敏感检查 text 是否匹配任一正则模式。"""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def classify_intent(
    message: str,
    *,
    mode: str = "chat",
) -> tuple[AgentName, str]:
    """
    基于正则的意图分类器。

    参数:
        message: 用户输入文本
        mode: 对话模式（chat / math）

    返回:
        (agent_name, route_reason) 二元组
        agent_name: 目标 Agent 标识（general/theory/experiment/literature）
        route_reason: 分类依据说明（用于 SSE meta 事件与日志）

    分类逻辑：
        1. mode=math → theory（数学推导确定路由，不检查关键词）
        2. 空消息 → general
        3. 按文献 > 实验 > 理论的优先级检查关键词
        4. 未匹配 → general
    """
    if mode == "math":
        return "theory", "mode=math"

    text = message.strip()
    if not text:
        return "general", "empty_message"

    # 优先级：literature > experiment > theory > general
    # 文献必定高于实验，因为"查论文的实验"是文献请求
    if _matches_any(text, _LITERATURE_PATTERNS):
        return "literature", "keyword:literature"

    if _matches_any(text, _EXPERIMENT_PATTERNS):
        return "experiment", "keyword:experiment"

    if _matches_any(text, _THEORY_PATTERNS):
        return "theory", "keyword:theory"

    return "general", "default"

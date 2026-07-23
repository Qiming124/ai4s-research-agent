# =============================================================================
# 意图分类：基于正则匹配的规则路由。
#
# 职责：根据用户消息中的关键词，决定应路由到哪个子 Agent。
#       这是 Phase 3 的轻量路由方案；LLM 分类见 router_llm.py。
#
# 分类优先级（从高到低）：
#     1. 显式 mode=math → theory
#     2. 审稿关键词 → review
#     3. 反例关键词 → counterexample
#     4. 文献相关关键词 → literature
#     5. 实验相关关键词 → experiment
#     6. 理论相关关键词 → theory
#     7. 未命中 → general
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
    r"形式化",
    r"损失函数",
    r"优化理论",
    r"收敛",
    r"不等式",
    r"引理",
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
    r"实验计划",
    r"回传",
    r"缺数",
    r"对照实验",
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

# ── 审稿关键词 ───────────────────────────────────────────────
_REVIEW_PATTERNS = [
    r"\breview\b",
    r"\breferee\b",
    r"审稿",
    r"审查",
    r"严谨性",
    r"证明缺口",
    r"是否可入库",
    r"小修",
    r"大修",
    r"拒稿",
]

# ── 反例关键词 ───────────────────────────────────────────────
_COUNTEREXAMPLE_PATTERNS = [
    r"\bcounterexample\b",
    r"\brefut",
    r"反例",
    r"推翻",
    r"证伪",
    r"使假设失效",
    r"构造.*失效",
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
        agent_name: 目标 Agent 标识
        route_reason: 分类依据说明（用于 SSE meta 事件与日志）

    分类逻辑：
        1. mode=math → theory
        2. 空消息 → general
        3. review > counterexample > literature > experiment > theory > general
    """
    if mode == "math":
        return "theory", "mode=math"

    text = message.strip()
    if not text:
        return "general", "empty_message"

    # 审稿/反例优先于宽泛的「证明」类 theory 词，避免「审这份证明」误进 theory
    if _matches_any(text, _REVIEW_PATTERNS):
        return "review", "keyword:review"

    if _matches_any(text, _COUNTEREXAMPLE_PATTERNS):
        return "counterexample", "keyword:counterexample"

    # 文献高于实验：「查论文的实验」仍偏文献
    if _matches_any(text, _LITERATURE_PATTERNS):
        return "literature", "keyword:literature"

    if _matches_any(text, _EXPERIMENT_PATTERNS):
        return "experiment", "keyword:experiment"

    if _matches_any(text, _THEORY_PATTERNS):
        return "theory", "keyword:theory"

    return "general", "default"

# =============================================================================
# LLM 意图路由：轻量模型分类 + 规则回退。
#
# 职责：
#     1. ROUTER_USE_LLM=true 时调用 Chat 模型输出 JSON 分类结果
#     2. 解析失败或异常时回退 server/graph/router.py 规则路由
#     3. 提供 classify_intent_smart() 统一入口
#
# 架构位置：
#     - 被调用：server/agents/orchestrator.py（resolve_target_agent）
#     - 调用：server/graph/router.py、server/langchain/llm.py、agents/config.py
#
# 阅读提示：
#     - 新人先看 classify_intent_smart 与 _ROUTER_PROMPT
#
# Debug：
#     - 总路由 general → LLM JSON 解析失败，查 logger warning
#     - 路由慢 → 轻量模型未配置或每次新建 client
# =============================================================================

from __future__ import annotations

import json
import logging
import re

from server.agents.config import AgentName, normalize_agent_name
from server.config import Settings, get_settings
from server.graph.router import classify_intent
from server.langchain.llm import get_chat_model

logger = logging.getLogger(__name__)

_ROUTER_PROMPT = """你是多 Agent 系统的路由分类器。根据用户消息选择唯一的目标 Agent。

可选 Agent：
- general：通用问答与总结
- theory：数学推导、定理证明、损失函数理论
- experiment：实验日志、训练指标、过拟合分析
- literature：文献检索、论文综述、引用

仅输出 JSON，不要 markdown：{"agent": "<name>", "reason": "<简短理由>"}

用户消息：
{message}
"""


async def classify_intent_llm(
    message: str,
    *,
    mode: str = "chat",
    settings: Settings | None = None,
) -> tuple[AgentName, str]:
    """用 LLM 分类意图；mode=math 时直接返回 theory。"""
    if mode == "math":
        return "theory", "mode=math"

    cfg = settings or get_settings()
    text = message.strip()
    if not text:
        return "general", "empty_message"

    model = get_chat_model(cfg, enable_thinking=False)
    prompt = _ROUTER_PROMPT.format(message=text[:2000])
    response = await model.ainvoke([{"role": "user", "content": prompt}])
    content = getattr(response, "content", None) or str(response)

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"LLM router 未返回 JSON: {content[:200]}")

    data = json.loads(match.group())
    agent = normalize_agent_name(str(data.get("agent", "")))
    if agent is None:
        raise ValueError(f"LLM router 返回无效 agent: {data.get('agent')}")

    reason = str(data.get("reason", "llm_router")).strip() or "llm_router"
    return agent, f"llm:{reason}"


async def classify_intent_smart(
    message: str,
    *,
    mode: str = "chat",
    settings: Settings | None = None,
) -> tuple[AgentName, str]:
    """ROUTER_USE_LLM 时尝试 LLM 路由，失败则回退关键词规则。"""
    cfg = settings or get_settings()
    if cfg.router_use_llm:
        try:
            return await classify_intent_llm(message, mode=mode, settings=cfg)
        except Exception as exc:
            logger.warning("LLM 路由失败，回退规则路由: %s", exc)
    return classify_intent(message, mode=mode)

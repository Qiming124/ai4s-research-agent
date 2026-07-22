# AI 提示词优化：多风格生成、打分对比与择优推荐。

from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.llm.client import get_deepseek_client
from server.llm.prompt_templates import get_template, list_templates

logger = logging.getLogger(__name__)

_SCORE_KEYS = ("clarity", "specificity", "verifiability", "structure")

_SYSTEM_PROMPT = """你是科研提示词工程专家，熟悉 RCCF、IMRaD、方法论约束（PRISMA/可复现）、PBTM 迭代研究等模板。
用户会提供原始提示、可选语境与优化目标。你需要：
1. 按给定的每种风格模板，各生成一条优化后的中文提示词（保留用户核心意图，不捏造新事实需求）
2. 对每条从 clarity/specificity/verifiability/structure 四维打分（0-10 整数）
3. 选出总分最高者作为推荐，并给出简短择优理由

严格只输出 JSON，不要 markdown 围栏，格式：
{
  "variants": [
    {
      "style_id": "rccf",
      "prompt": "优化后的完整提示词",
      "scores": {"clarity": 8, "specificity": 9, "verifiability": 7, "structure": 8},
      "highlights": ["亮点1", "亮点2"]
    }
  ],
  "recommended_style_id": "rccf",
  "rationale": "择优理由（1-3句）"
}"""


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*\n([\s\S]*?)\n```\s*$", text, flags=re.I)
    if m:
        return m.group(1).strip()
    return text


def _total_score(scores: dict[str, Any]) -> int:
    return sum(int(scores.get(k, 0) or 0) for k in _SCORE_KEYS)


def _fallback_variant(style_id: str, raw: str, context: str, goal: str) -> dict[str, Any]:
    tpl = get_template(style_id)
    if not tpl:
        return {}
    name = tpl["name_zh"]
    prompt = (
        f"【{name} 优化】\n"
        f"原始需求：{raw.strip()}\n"
    )
    if context.strip():
        prompt += f"语境：{context.strip()}\n"
    if goal.strip():
        prompt += f"优化目标：{goal.strip()}\n"
    prompt += (
        f"\n请按以下结构回答：\n{tpl['skeleton']}\n"
        f"\n要求：专业、可验证、不捏造数据或文献。"
    )
    base = 6 if raw.strip() else 4
    scores = {k: base for k in _SCORE_KEYS}
    return {
        "style_id": style_id,
        "style_name": tpl["name"],
        "style_name_zh": tpl["name_zh"],
        "prompt": prompt,
        "scores": scores,
        "total_score": _total_score(scores),
        "highlights": [f"基于 {name} 模板结构化"],
    }


def _enrich_variant(item: dict[str, Any]) -> dict[str, Any]:
    style_id = str(item.get("style_id", ""))
    tpl = get_template(style_id)
    scores = item.get("scores") or {}
    if isinstance(scores, dict):
        scores = {k: int(scores.get(k, 0) or 0) for k in _SCORE_KEYS}
    else:
        scores = {k: 0 for k in _SCORE_KEYS}
    return {
        "style_id": style_id,
        "style_name": tpl["name"] if tpl else style_id,
        "style_name_zh": tpl["name_zh"] if tpl else style_id,
        "prompt": str(item.get("prompt", "")).strip(),
        "scores": scores,
        "total_score": _total_score(scores),
        "highlights": list(item.get("highlights") or []),
    }


def _pick_recommended(variants: list[dict[str, Any]]) -> tuple[str, str]:
    if not variants:
        return "", ""
    best = max(variants, key=lambda v: v.get("total_score", 0))
    return best["style_id"], (
        f"在 {len(variants)} 种风格中，{best['style_name_zh']}（{best['style_id']}）"
        f"综合得分最高（{best['total_score']}/40）。"
    )


def _build_user_message(
    *,
    text: str,
    context: str,
    goal: str,
    mode: str,
    agent: str | None,
    style_ids: list[str] | None,
) -> str:
    styles = style_ids or [t["id"] for t in list_templates()]
    style_blocks = []
    for sid in styles:
        tpl = get_template(sid)
        if tpl:
            style_blocks.append(
                f"### 风格 {sid} ({tpl['name_zh']})\n"
                f"说明：{tpl['description']}\n"
                f"骨架：\n{tpl['skeleton']}\n"
                f"适用：{', '.join(tpl['best_for'])}"
            )
    parts = [
        f"原始提示词：\n{text.strip()}",
        f"对话模式：{mode or 'chat'}",
    ]
    if agent:
        parts.append(f"目标 Agent：{agent}")
    if context.strip():
        parts.append(f"补充语境：\n{context.strip()}")
    if goal.strip():
        parts.append(f"优化目标：\n{goal.strip()}")
    parts.append("请为以下每种风格各生成一条优化提示词并打分：\n" + "\n\n".join(style_blocks))
    return "\n\n".join(parts)


def _parse_llm_result(raw: str, *, text: str, context: str, goal: str) -> dict[str, Any]:
    try:
        data = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        logger.warning("提示词优化 JSON 解析失败，使用模板回退")
        return _fallback_result(text, context, goal)

    variants = [_enrich_variant(v) for v in (data.get("variants") or []) if v.get("prompt")]
    variants = [v for v in variants if v["prompt"]]
    if not variants:
        return _fallback_result(text, context, goal)

    rec_id = str(data.get("recommended_style_id") or "")
    rationale = str(data.get("rationale") or "").strip()
    if rec_id not in {v["style_id"] for v in variants}:
        rec_id, auto_rationale = _pick_recommended(variants)
        rationale = rationale or auto_rationale
    recommended = next((v for v in variants if v["style_id"] == rec_id), variants[0])
    return {
        "variants": variants,
        "recommended_style_id": recommended["style_id"],
        "recommended_prompt": recommended["prompt"],
        "rationale": rationale,
        "ai_applied": True,
    }


def _fallback_result(text: str, context: str, goal: str) -> dict[str, Any]:
    variants = [
        v
        for sid in [t["id"] for t in list_templates()]
        if (v := _fallback_variant(sid, text, context, goal))
    ]
    rec_id, rationale = _pick_recommended(variants)
    recommended = next((v for v in variants if v["style_id"] == rec_id), variants[0])
    return {
        "variants": variants,
        "recommended_style_id": rec_id,
        "recommended_prompt": recommended["prompt"],
        "rationale": rationale + "（AI 不可用，已用本地模板回退）",
        "ai_applied": False,
    }


async def optimize_user_prompt(
    *,
    text: str,
    context: str = "",
    goal: str = "",
    mode: str = "chat",
    agent: str | None = None,
    style_ids: list[str] | None = None,
) -> dict[str, Any]:
    """生成多风格优化提示词并择优。返回 variants、recommended_*、rationale、ai_applied。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("提示词不能为空")

    user_msg = _build_user_message(
        text=text,
        context=context,
        goal=goal,
        mode=mode,
        agent=agent,
        style_ids=style_ids,
    )

    try:
        client = get_deepseek_client()
        content, _, _ = await client.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            reasoning_effort="high",
            enable_thinking=False,
            max_tokens=4096,
        )
        result = _parse_llm_result(content or "", text=text, context=context, goal=goal)
        result["original"] = text
        return result
    except Exception as exc:
        logger.warning("提示词优化 LLM 调用失败: %s", exc)
        result = _fallback_result(text, context, goal)
        result["original"] = text
        return result

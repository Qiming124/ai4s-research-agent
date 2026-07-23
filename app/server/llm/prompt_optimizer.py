# AI 提示词优化：在忠实原问的前提下做结构化改写；禁止换题/编造背景。

from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.llm.client import get_deepseek_client
from server.llm.prompt_templates import get_template, list_templates

logger = logging.getLogger(__name__)

_SCORE_KEYS = ("clarity", "specificity", "verifiability", "structure")

# 英文词过短不计入「新造词」检测；常见功能词忽略
_STOP_EN = {
    "the", "and", "for", "with", "from", "that", "this", "your", "you",
    "are", "was", "were", "have", "has", "not", "but", "use", "using",
    "please", "only", "into", "about", "when", "then", "than", "also",
    "must", "should", "will", "can", "may", "each", "step", "list",
    "output", "format", "task", "role", "context", "constraint",
    "markdown", "section", "sections", "based", "given", "user",
}

_SYSTEM_PROMPT = """你是言晖科研助手的「提示词改写器」。

目标：把用户的原始提问改写成更清晰、可执行的提示词，方便发给科研 Agent。

## 硬性忠实规则（违反则整次失败）
1. **不换题**：优化后的提示必须仍在回答「同一个问题」；核心对象、数值、专有名词必须保留。
2. **不编造**：禁止添加用户原文与「补充语境」中都未出现的：
   - 算法/模型名（如 TRPO、ResNet、AdamW…）
   - 定理/引理编号（如「定理 1」除非原文有）
   - 数据集、网络结构、实验设定、论文标题
   - 背景故事或「正在研究某某」的虚构课题叙述
3. **缺信息就写「待用户补充」**，不要用猜测填满。
4. **风格模板只影响结构**（角色/分步/格式），不改变科学内容。
5. 若原文是检索请求，优化后仍须是检索请求；若是证明题，仍须是证明题；若是读表比较，仍须是读表比较。

## 输出
严格只输出 JSON（不要 markdown 围栏）：
{
  "variants": [
    {
      "style_id": "clarify",
      "prompt": "优化后的完整提示词",
      "scores": {"clarity": 8, "specificity": 8, "verifiability": 8, "structure": 8},
      "highlights": ["亮点1"]
    }
  ],
  "recommended_style_id": "clarify",
  "rationale": "择优理由（1-2句，须说明为何仍忠实原问）"
}

打分时：若某变体引入原文没有的专有名词或换题，将该变体各维分数压到 ≤3。
"""


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*\n([\s\S]*?)\n```\s*$", text, flags=re.I)
    if m:
        return m.group(1).strip()
    return text


def _total_score(scores: dict[str, Any]) -> int:
    return sum(int(scores.get(k, 0) or 0) for k in _SCORE_KEYS)


def extract_anchors(text: str) -> set[str]:
    """从原问抽取必须保留的锚点：数字、英文词、较长中文片段。"""
    text = text or ""
    anchors: set[str] = set()
    for m in re.findall(r"\d+(?:\.\d+)?", text):
        anchors.add(m)
    for m in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}", text):
        if m.lower() not in _STOP_EN:
            anchors.add(m)
    for m in re.findall(r"[\u4e00-\u9fff]{2,8}", text):
        anchors.add(m)
    return anchors


def english_content_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for m in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", text or ""):
        low = m.lower()
        if low not in _STOP_EN:
            out.add(low)
    return out


def fidelity_report(original: str, optimized: str) -> dict[str, Any]:
    """评估优化提示对原问的忠实度。"""
    anchors = extract_anchors(original)
    opt_l = (optimized or "").lower()
    hit = 0
    missing: list[str] = []
    for a in anchors:
        if a.lower() in opt_l or a in (optimized or ""):
            hit += 1
        else:
            missing.append(a)
    anchor_ratio = 1.0 if not anchors else hit / len(anchors)

    orig_en = english_content_tokens(original)
    new_en = english_content_tokens(optimized) - orig_en
    # 允许少量结构词；过多新英文专名视为编造
    invent_penalty = min(1.0, len(new_en) / 4.0)

    ok = anchor_ratio >= 0.7 and len(new_en) <= 3
    return {
        "ok": ok,
        "anchor_ratio": round(anchor_ratio, 3),
        "missing_anchors": missing[:12],
        "new_english": sorted(new_en)[:12],
        "invent_penalty": round(invent_penalty, 3),
    }


def _safe_structured_rewrite(raw: str, context: str, goal: str) -> str:
    """确定性忠实改写：包一层结构，绝不改写科学内容。"""
    parts = [
        "请完成以下用户问题（保持原意，不要改换主题或编造未提及的设定）：",
        "",
        raw.strip(),
    ]
    if context.strip():
        parts.extend(["", "补充语境（仅供参考，勿扩展为虚构背景）：", context.strip()])
    parts.extend(
        [
            "",
            "回答要求：",
            "1. 紧扣上述原文中的对象、数值与诉求；",
            "2. 缺信息时明确列出待补充项，禁止猜测补全算法名/定理编号/实验设定；",
            "3. 输出结构清晰（分步或分节），结论可核对。",
        ]
    )
    if goal.strip():
        parts.extend(["", f"额外优化目标（不得覆盖忠实性）：{goal.strip()}"])
    return "\n".join(parts)


def _fallback_variant(style_id: str, raw: str, context: str, goal: str) -> dict[str, Any]:
    tpl = get_template(style_id)
    if not tpl:
        return {}
    name = tpl["name_zh"]
    # 回退也必须忠实：用安全改写，而不是填满 skeleton 占位符造成「像换题」
    prompt = _safe_structured_rewrite(raw, context, goal)
    if style_id == "structural":
        prompt += (
            "\n\n请按可验证步骤组织："
            "\n1. 复述问题与已知量；\n2. 核心推导/检索/读数；\n3. 自检是否答全原问。"
        )
    elif style_id == "rccf":
        prompt = (
            f"你是一位科研助手。\n任务：\n{raw.strip()}\n"
            + (f"\n补充语境：\n{context.strip()}\n" if context.strip() else "")
            + "\n约束：不要引入原文未出现的算法、定理编号或实验设定；缺信息先说明。"
            "\n输出：结构清晰的分节或列表。"
        )
    scores = {k: 7 for k in _SCORE_KEYS}
    return {
        "style_id": style_id,
        "style_name": tpl["name"],
        "style_name_zh": name,
        "prompt": prompt,
        "scores": scores,
        "total_score": _total_score(scores),
        "highlights": ["忠实原问的结构化改写"],
        "fidelity": fidelity_report(raw, prompt),
    }


def _enrich_variant(item: dict[str, Any], *, original: str) -> dict[str, Any]:
    style_id = str(item.get("style_id", ""))
    tpl = get_template(style_id)
    scores = item.get("scores") or {}
    if isinstance(scores, dict):
        scores = {k: int(scores.get(k, 0) or 0) for k in _SCORE_KEYS}
    else:
        scores = {k: 0 for k in _SCORE_KEYS}
    prompt = str(item.get("prompt", "")).strip()
    fid = fidelity_report(original, prompt)
    if not fid["ok"]:
        # 压分，避免不忠实变体被推荐
        scores = {k: min(scores.get(k, 0), 3) for k in _SCORE_KEYS}
    return {
        "style_id": style_id,
        "style_name": tpl["name"] if tpl else style_id,
        "style_name_zh": tpl["name_zh"] if tpl else style_id,
        "prompt": prompt,
        "scores": scores,
        "total_score": _total_score(scores),
        "highlights": list(item.get("highlights") or []),
        "fidelity": fid,
    }


def _pick_recommended(variants: list[dict[str, Any]]) -> tuple[str, str]:
    if not variants:
        return "", ""
    faithful = [v for v in variants if (v.get("fidelity") or {}).get("ok", False)]
    pool = faithful or variants
    best = max(pool, key=lambda v: v.get("total_score", 0))
    note = ""
    if faithful and len(faithful) < len(variants):
        note = "（已排除未通过忠实度检查的变体）"
    return best["style_id"], (
        f"在 {len(pool)} 种可用风格中，{best['style_name_zh']}（{best['style_id']}）"
        f"综合得分最高（{best['total_score']}/40）。{note}"
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
                f"骨架（只学结构，勿填虚构内容）：\n{tpl['skeleton']}\n"
                f"适用：{', '.join(tpl['best_for'])}"
            )
    anchors = sorted(extract_anchors(text))
    parts = [
        "【原始提示词——必须保持同一问题】\n" + text.strip(),
        f"对话模式：{mode or 'chat'}",
        "必须保留的锚点（优化后仍须出现）：" + ("、".join(anchors) if anchors else "（无特殊锚点）"),
    ]
    if agent:
        parts.append(f"目标 Agent：{agent}")
    if context.strip():
        parts.append("【补充语境——可引用，禁止借此编造新课题】\n" + context.strip())
    if goal.strip():
        parts.append(
            "【优化目标——不得覆盖忠实性】\n"
            + goal.strip()
            + "\n（若与忠实规则冲突，以忠实原问为准）"
        )
    parts.append(
        "请为以下每种风格各生成一条优化提示词并打分。"
        "记住：四种风格说的是同一道原题，只是结构不同。\n"
        + "\n\n".join(style_blocks)
    )
    return "\n\n".join(parts)


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
        "rationale": rationale + "（AI 不可用或未通过忠实检查，已用本地忠实改写）",
        "ai_applied": False,
    }


def _parse_llm_result(raw: str, *, text: str, context: str, goal: str) -> dict[str, Any]:
    try:
        data = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        logger.warning("提示词优化 JSON 解析失败，使用忠实回退")
        return _fallback_result(text, context, goal)

    variants = [
        _enrich_variant(v, original=text)
        for v in (data.get("variants") or [])
        if v.get("prompt")
    ]
    variants = [v for v in variants if v["prompt"]]
    if not variants:
        return _fallback_result(text, context, goal)

    # 过滤不忠实变体；若全部失败则整体回退
    faithful = [v for v in variants if (v.get("fidelity") or {}).get("ok")]
    if not faithful:
        logger.warning(
            "提示词优化全部变体未通过忠实度检查，回退。samples=%s",
            [(v["style_id"], v.get("fidelity")) for v in variants[:4]],
        )
        return _fallback_result(text, context, goal)

    variants = faithful
    rec_id = str(data.get("recommended_style_id") or "")
    rationale = str(data.get("rationale") or "").strip()
    if rec_id not in {v["style_id"] for v in variants}:
        rec_id, auto_rationale = _pick_recommended(variants)
        rationale = rationale or auto_rationale
    recommended = next((v for v in variants if v["style_id"] == rec_id), variants[0])
    # 最终再检一次推荐项
    if not (recommended.get("fidelity") or {}).get("ok"):
        return _fallback_result(text, context, goal)

    return {
        "variants": variants,
        "recommended_style_id": recommended["style_id"],
        "recommended_prompt": recommended["prompt"],
        "rationale": rationale or _pick_recommended(variants)[1],
        "ai_applied": True,
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
    """生成多风格优化提示词并择优；不忠实原问的结果会被丢弃或回退。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("提示词不能为空")

    # 默认目标强调忠实，避免「更专业」诱导编造背景
    if not (goal or "").strip():
        goal = "更清晰可执行，但必须保持与原问同一主题，禁止编造未提及设定"

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

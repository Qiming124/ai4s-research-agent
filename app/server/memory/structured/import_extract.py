# =============================================================================
# 从论文文本抽取定理/引理候选，供 L4 导入预览（不写库）。
# =============================================================================

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_IMPORT_SYSTEM = """你是科研文献结构化抽取助手。从用户给出的论文正文中抽取定理、引理、推论、假设与关键定义/公式。

规则：
1. 只抽取原文中确实存在的陈述，禁止编造。
2. 公式用 LaTeX，行内 $...$，独立公式 $$...$$。
3. kind 只能是：theorem（定理/引理/推论）、hypothesis（假设）、note（定义/公式摘录/其它）。
4. 若文中有页码注释 <!-- page N -->，尽量填写 page。
5. confidence 为 0~1；不确定则降低并仍可输出。
6. 只输出一个 JSON 数组，不要 markdown 围栏，不要其它说明。

每项格式：
{"kind":"theorem","title":"...","body":"...","page":1,"confidence":0.8}
"""

_KIND_MAP = {
    "theorem": "theorem",
    "lemma": "theorem",
    "corollary": "theorem",
    "定理": "theorem",
    "引理": "theorem",
    "推论": "theorem",
    "hypothesis": "hypothesis",
    "assumption": "hypothesis",
    "假设": "hypothesis",
    "note": "note",
    "definition": "note",
    "定义": "note",
}


def _strip_json_fence(text: str) -> str:
    raw = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", raw, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return raw


def _normalize_kind(raw: Any) -> str:
    key = str(raw or "note").strip().lower()
    if key in ("theorem", "hypothesis", "conclusion", "citation", "note"):
        return key
    return _KIND_MAP.get(key, "note")


def parse_import_candidates_json(content: str) -> list[dict[str, Any]]:
    """解析 LLM 返回的候选 JSON 数组。"""
    raw = _strip_json_fence(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试截取第一个 [...] 数组
        start = raw.find("[")
        end = raw.rfind("]")
        if start < 0 or end <= start:
            logger.warning("导入候选 JSON 解析失败")
            return []
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        body = str(item.get("body") or "").strip()
        title = str(item.get("title") or "").strip()
        if not body and not title:
            continue
        if not body:
            body = title
        conf = item.get("confidence", 0.5)
        try:
            confidence = float(conf)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        page = item.get("page")
        page_int: int | None
        try:
            page_int = int(page) if page is not None else None
        except (TypeError, ValueError):
            page_int = None
        out.append(
            {
                "kind": _normalize_kind(item.get("kind")),
                "title": title or body[:60],
                "body": body,
                "page": page_int,
                "confidence": confidence,
                "selected_default": confidence >= 0.45,
            }
        )
    return out


def candidates_from_markdown(content: str) -> list[dict[str, Any]]:
    """复用 ## 定理/引理 规则做 Markdown 预览。"""
    from server.memory.structured.extract import extract_structured_entries

    entries = extract_structured_entries(content)
    out: list[dict[str, Any]] = []
    for e in entries:
        out.append(
            {
                "kind": e.get("kind") or "theorem",
                "title": e.get("title") or "",
                "body": e.get("body") or "",
                "page": None,
                "confidence": 1.0,
                "selected_default": True,
            }
        )
    return out


async def extract_candidates_with_llm(text: str) -> list[dict[str, Any]]:
    """调用 LLM 从全文抽取候选（不为省 token 截断）。"""
    from server.llm.client import get_deepseek_client

    client = get_deepseek_client()
    messages = [
        {"role": "system", "content": _IMPORT_SYSTEM},
        {
            "role": "user",
            "content": "请从以下论文正文抽取条目，输出 JSON 数组：\n\n" + text,
        },
    ]
    content, _reasoning, _usage = await client.chat(
        messages,
        enable_thinking=False,
        max_tokens=8192,
    )
    return parse_import_candidates_json(content or "")

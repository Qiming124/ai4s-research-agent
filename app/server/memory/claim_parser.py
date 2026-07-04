# 结构化可验证 Claim 解析：从 Theory Agent 输出提取 verifiable 块。

from __future__ import annotations

import json
import re
from typing import Any

import yaml

_VERIFIABLE_FENCE = re.compile(
    r"```(?:yaml|yml|json)?\s*\n(verifiable:[\s\S]*?)\n```",
    re.IGNORECASE,
)
_VERIFIABLE_INLINE = re.compile(
    r"^verifiable:\s*\n([\s\S]*?)(?=\n##|\n```|\Z)",
    re.MULTILINE,
)


def parse_verifiable_claim(content: str) -> dict[str, Any] | None:
    """从推导文本解析 verifiable Claim 块。"""
    if not content.strip():
        return None

    for pattern in (_VERIFIABLE_FENCE, _VERIFIABLE_INLINE):
        match = pattern.search(content)
        if not match:
            continue
        raw = match.group(1).strip()
        if not raw.startswith("verifiable"):
            raw = f"verifiable:\n{raw}"
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict) and "verifiable" in data:
                claim = data["verifiable"]
                if isinstance(claim, dict) and claim.get("expression"):
                    return _normalize_claim(claim)
        except yaml.YAMLError:
            pass
        try:
            blob = json.loads(raw if raw.startswith("{") else match.group(0))
            if isinstance(blob, dict):
                claim = blob.get("verifiable", blob)
                if isinstance(claim, dict) and claim.get("expression"):
                    return _normalize_claim(claim)
        except json.JSONDecodeError:
            continue
    return None


def _normalize_claim(claim: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "expression": str(claim.get("expression", "")).strip(),
        "point": str(claim.get("point", "0,0")).strip(),
        "variables": str(claim.get("variables", "x0,x1")).strip(),
        "tier_hint": str(claim.get("tier_hint", "symbolic")).strip(),
        "assumptions": list(claim.get("assumptions") or []),
    }
    expected = claim.get("expected")
    if isinstance(expected, dict):
        out["expected"] = expected
    elif expected:
        out["expected"] = {"classification": str(expected)}
    else:
        out["expected"] = {}
    return out


def claim_from_content_or_expression(content: str, fallback_expr: str | None = None) -> dict[str, Any] | None:
    """优先解析结构化 Claim，否则用启发式表达式构造最小 Claim。"""
    parsed = parse_verifiable_claim(content)
    if parsed:
        return parsed
    if fallback_expr:
        return {
            "expression": fallback_expr,
            "point": "0,0",
            "variables": "x0,x1",
            "tier_hint": "numerical",
            "assumptions": [],
            "expected": {},
        }
    return None

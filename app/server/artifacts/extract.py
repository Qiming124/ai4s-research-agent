# =============================================================================
# 从 Agent Markdown 中解析 ```artifact:Type ... ``` JSON 围栏。
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from shared.artifact_models import ArtifactType

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(
    r"```artifact:(DerivationTrace|ExperimentPlan|DataPacket|NextStepMemo)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_VALID_TYPES: set[str] = {
    "DerivationTrace",
    "ExperimentPlan",
    "DataPacket",
    "NextStepMemo",
}


def _as_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_as_str(v) for v in value]
        return "；".join(p for p in parts if p)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            vs = _as_str(v)
            parts.append(f"{k}: {vs}" if vs else str(k))
        return "；".join(parts)
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                s = _as_str(item)
            else:
                s = _as_str(item)
            if s:
                out.append(s)
        return out
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            if isinstance(v, bool):
                out.append(str(k) if v else f"{k}=false")
            elif v is None or v == "":
                out.append(str(k))
            else:
                out.append(f"{k}: {_as_str(v)}")
        return out
    s = _as_str(value).strip()
    if not s:
        return []
    # LLM 常把步骤写成一整段：按换行或「1) / 1. / 1、」切开
    if "\n" in s:
        parts = [p.strip(" -\t") for p in s.splitlines() if p.strip()]
        if len(parts) > 1:
            return parts
    numbered = re.split(r"(?=(?<!\d)\d+\s*[)）.、])", s)
    parts = [p.strip(" ；;\t") for p in numbered if p and p.strip(" ；;\t")]
    if len(parts) > 1:
        # 若首段只是前缀标签（无编号），并入下一段
        if parts[0] and not re.match(r"\d+\s*[)）.、]", parts[0]) and len(parts) >= 2:
            parts[1] = f"{parts[0]} {parts[1]}".strip()
            parts = parts[1:]
        return parts
    return [s]


def _as_str_dict(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): _as_str(v) for k, v in value.items()}
    return {}


def _normalize_derivation_steps(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, str):
        return [
            {"title": f"步骤 {i + 1}", "body": step, "status": "pending"}
            for i, step in enumerate(_as_str_list(value))
        ]
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for i, item in enumerate(value):
        if isinstance(item, dict):
            status = item.get("status", "pending")
            if status not in ("proven", "pending", "heuristic"):
                status_l = str(status).lower()
                if status_l in ("proved", "done", "ok", "verified"):
                    status = "proven"
                elif status_l in ("guess",):
                    status = "heuristic"
                else:
                    status = "pending"
            title = (
                _as_str(item.get("title"))
                or _as_str(item.get("claim"))
                or _as_str(item.get("id"))
                or _as_str(item.get("name"))
                or f"步骤 {i + 1}"
            )
            body = (
                _as_str(item.get("body"))
                or _as_str(item.get("proof"))
                or _as_str(item.get("content"))
                or _as_str(item.get("statement"))
            )
            if not body:
                skip = {
                    "title",
                    "body",
                    "status",
                    "claim",
                    "id",
                    "name",
                    "proof",
                    "content",
                    "statement",
                }
                rest = {k: v for k, v in item.items() if k not in skip}
                body = _as_str(rest) if rest else ""
            out.append({"title": title, "body": body, "status": status})
        else:
            text = _as_str(item)
            if text:
                out.append({"title": f"步骤 {i + 1}", "body": text, "status": "pending"})
    return out


def _coerce_derivation_trace_from_alt_shape(data: dict[str, Any]) -> dict[str, Any]:
    """
    兼容模型自创结构（problem/definitions/lemmas/theorem/verification），
    映射为 title + steps + claim_yaml，避免面板空壳。
    """
    out = dict(data)
    steps = _normalize_derivation_steps(out.get("steps"))

    definitions = out.get("definitions")
    if isinstance(definitions, dict) and definitions:
        steps.append({"title": "定义 / 符号", "body": _as_str(definitions), "status": "proven"})
    elif isinstance(definitions, list) and definitions:
        steps.extend(_normalize_derivation_steps(definitions))

    assumptions = out.get("assumptions")
    if assumptions:
        if isinstance(assumptions, list):
            body = "；".join(_as_str(a) for a in assumptions if _as_str(a))
        else:
            body = _as_str(assumptions)
        if body:
            steps.append({"title": "假设", "body": body, "status": "proven"})

    lemmas = out.get("lemmas")
    if lemmas:
        for i, lem in enumerate(lemmas if isinstance(lemmas, list) else [lemmas]):
            if not isinstance(lem, dict):
                text = _as_str(lem)
                if text:
                    steps.append({"title": f"引理 {i + 1}", "body": text, "status": "proven"})
                continue
            claim = _as_str(lem.get("claim") or lem.get("statement") or lem.get("title"))
            proof = _as_str(lem.get("proof") or lem.get("body"))
            lid = _as_str(lem.get("id")) or f"lemma_{i + 1}"
            title = (claim or lid)[:120]
            if claim and proof:
                body = f"**陈述**：{claim}\n\n**证明**：{proof}"
            else:
                body = proof or claim
            steps.append({"title": title, "body": body, "status": "proven"})

    theorem = out.get("theorem")
    if isinstance(theorem, dict) and theorem:
        stmt = _as_str(theorem.get("statement") or theorem.get("claim"))
        proof = _as_str(theorem.get("proof") or theorem.get("body"))
        extra = {
            k: v
            for k, v in theorem.items()
            if k not in ("statement", "claim", "proof", "body")
        }
        body_parts: list[str] = []
        if stmt:
            body_parts.append(f"**陈述**：{stmt}")
        if proof:
            body_parts.append(f"**证明**：{proof}")
        if extra:
            body_parts.append(_as_str(extra))
        steps.append(
            {
                "title": (stmt[:120] if stmt else "定理"),
                "body": "\n\n".join(body_parts) or _as_str(theorem),
                "status": "proven",
            }
        )
    elif isinstance(theorem, str) and theorem.strip():
        steps.append({"title": "定理", "body": theorem.strip(), "status": "proven"})

    verification = out.get("verification")
    if verification:
        steps.append({"title": "核验", "body": _as_str(verification), "status": "proven"})

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for st in steps:
        key = (st.get("title") or "", st.get("body") or "")
        if key in seen or (not key[0] and not key[1]):
            continue
        seen.add(key)
        deduped.append(st)
    out["steps"] = deduped

    title = out.get("title")
    if not title or not str(title).strip():
        th_stmt = None
        if isinstance(theorem, dict):
            th_stmt = theorem.get("statement")
        for candidate in (out.get("problem"), out.get("name"), th_stmt):
            t = _as_str(candidate).strip()
            if t:
                out["title"] = t[:120]
                break
    elif not isinstance(title, str):
        out["title"] = _as_str(title)

    claim = out.get("claim_yaml")
    if claim is not None and not isinstance(claim, str):
        try:
            out["claim_yaml"] = json.dumps(claim, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            out["claim_yaml"] = _as_str(claim)
    elif not claim:
        for key in ("verifiable", "verification"):
            raw = out.get(key)
            if isinstance(raw, dict) and raw:
                blob = {"verifiable": raw} if key == "verification" else raw
                try:
                    out["claim_yaml"] = json.dumps(blob, ensure_ascii=False, indent=2)
                except (TypeError, ValueError):
                    out["claim_yaml"] = _as_str(raw)
                break

    for k in (
        "problem",
        "definitions",
        "assumptions",
        "lemmas",
        "theorem",
        "verification",
        "verifiable",
        "name",
    ):
        out.pop(k, None)
    return out


def normalize_artifact_payload(artifact_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 常见的类型偏差收成 schema 可接受的形状。"""
    data = dict(payload)
    if artifact_type == "DerivationTrace":
        alt_keys = (
            "lemmas",
            "theorem",
            "definitions",
            "assumptions",
            "verification",
            "verifiable",
            "problem",
        )
        needs_coerce = (not data.get("steps")) or any(k in data for k in alt_keys)
        if needs_coerce:
            data = _coerce_derivation_trace_from_alt_shape(data)

        if "title" in data and data["title"] is None:
            data["title"] = ""
        elif "title" in data and not isinstance(data.get("title"), str):
            data["title"] = _as_str(data.get("title"))
        if "claim_yaml" in data and data["claim_yaml"] is not None and not isinstance(
            data.get("claim_yaml"), str
        ):
            data["claim_yaml"] = _as_str(data.get("claim_yaml"))
        if "steps" in data:
            data["steps"] = _normalize_derivation_steps(data.get("steps"))
        # 兼容旧 MethodCard 关联字段：丢弃，不再持久化
        data.pop("method_card_ids", None)
        if "l4_ref_ids" in data:
            data["l4_ref_ids"] = _as_str_list(data.get("l4_ref_ids"))
    elif artifact_type == "ExperimentPlan":
        if "objectives" in data:
            data["objectives"] = _as_str(data.get("objectives"))
        for key in ("variables", "controls", "success_criteria", "record_fields"):
            if key in data:
                data[key] = _as_str_list(data.get(key))
        if "hyperparams" in data and not isinstance(data.get("hyperparams"), dict):
            raw = data.get("hyperparams")
            data["hyperparams"] = raw if isinstance(raw, dict) else {}
        for key in ("title", "notes", "revision_note", "claim_or_theorem_ref"):
            if key in data and data[key] is None:
                data[key] = ""
            elif key in data and not isinstance(data[key], str):
                data[key] = _as_str(data[key])
        status = data.get("status")
        if status not in ("planned", "active", "done", "superseded"):
            data["status"] = "planned"
        if data.get("parent_plan_id") is not None and not isinstance(data.get("parent_plan_id"), str):
            data["parent_plan_id"] = _as_str(data.get("parent_plan_id")) or None
    elif artifact_type == "NextStepMemo":
        for key in ("missing_data", "next_experiments"):
            if key in data:
                data[key] = _as_str_list(data.get(key))
        for key in ("title", "notes", "claim_ref", "data_packet_id"):
            if key in data and data[key] is None:
                data[key] = "" if key in ("title", "notes") else None
            elif key in ("title", "notes") and key in data and not isinstance(data[key], str):
                data[key] = _as_str(data[key])
            elif key == "data_packet_id" and key in data and data[key] is not None and not isinstance(
                data[key], str
            ):
                # 模型有时误传 list；取首个字符串
                if isinstance(data[key], list) and data[key]:
                    data[key] = _as_str(data[key][0]) or None
                else:
                    data[key] = _as_str(data[key]) or None
        verdict = data.get("verdict")
        if verdict not in ("supported", "refuted", "inconclusive"):
            data["verdict"] = "inconclusive"
    return data


def extract_artifacts_from_text(content: str) -> list[tuple[ArtifactType, dict[str, Any]]]:
    """
    解析文本中的 artifact 围栏。失败的块跳过，不抛异常。
    返回 [(type, payload_dict), ...]
    """
    if not content or "```artifact:" not in content:
        return []
    found: list[tuple[ArtifactType, dict[str, Any]]] = []
    for match in _FENCE_RE.finditer(content):
        raw_type = match.group(1)
        body = match.group(2).strip()
        # 规范化大小写
        artifact_type = next((t for t in _VALID_TYPES if t.lower() == raw_type.lower()), None)
        if not artifact_type:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.info("artifact 围栏 JSON 解析失败 type=%s", raw_type)
            continue
        if not isinstance(payload, dict):
            continue
        if not payload.get("id"):
            payload["id"] = str(uuid.uuid4())
        payload = normalize_artifact_payload(artifact_type, payload)
        found.append((artifact_type, payload))  # type: ignore[arg-type]
    return found

# 科研提示词测试案例：从 conf/prompt/test_cases.json 加载（可改文件无需改代码）。

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import TypedDict

from shared.paths import conf_path

logger = logging.getLogger(__name__)


class PromptTestCase(TypedDict):
    id: str
    title: str
    category: str
    raw_prompt: str
    context: str
    expected_traits: list[str]
    source_note: str


_REQUIRED = (
    "id",
    "title",
    "category",
    "raw_prompt",
    "context",
    "expected_traits",
    "source_note",
)


@lru_cache(maxsize=1)
def _load_cases() -> tuple[PromptTestCase, ...]:
    path = conf_path("prompt/test_cases.json")
    if not path.is_file():
        logger.warning("prompt test cases missing: %s", path)
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"test_cases.json 须为数组: {path}")
    out: list[PromptTestCase] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if any(k not in item for k in _REQUIRED):
            logger.warning("skip invalid test case keys=%s", list(item.keys()))
            continue
        out.append(
            {
                "id": str(item["id"]),
                "title": str(item["title"]),
                "category": str(item["category"]),
                "raw_prompt": str(item["raw_prompt"]),
                "context": str(item["context"]),
                "expected_traits": [str(x) for x in (item.get("expected_traits") or [])],
                "source_note": str(item["source_note"]),
            }
        )
    return tuple(out)


def reload_test_cases() -> None:
    _load_cases.cache_clear()


def list_test_cases() -> list[dict]:
    return [dict(c) for c in _load_cases()]


def get_test_case(case_id: str) -> PromptTestCase | None:
    for case in _load_cases():
        if case["id"] == case_id:
            return case
    return None

# 科研提示词风格模板：从 conf/prompt/templates.json 加载（可改文件无需改代码）。

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import TypedDict

from shared.paths import conf_path

logger = logging.getLogger(__name__)


class PromptStyleTemplate(TypedDict):
    id: str
    name: str
    name_zh: str
    description: str
    reference: str
    skeleton: str
    best_for: list[str]


_REQUIRED = ("id", "name", "name_zh", "description", "reference", "skeleton", "best_for")


@lru_cache(maxsize=1)
def _load_templates() -> tuple[PromptStyleTemplate, ...]:
    path = conf_path("prompt/templates.json")
    if not path.is_file():
        logger.warning("prompt templates missing: %s", path)
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"templates.json 须为数组: {path}")
    out: list[PromptStyleTemplate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if any(k not in item for k in _REQUIRED):
            logger.warning("skip invalid template entry keys=%s", list(item.keys()))
            continue
        out.append(
            {
                "id": str(item["id"]),
                "name": str(item["name"]),
                "name_zh": str(item["name_zh"]),
                "description": str(item["description"]),
                "reference": str(item["reference"]),
                "skeleton": str(item["skeleton"]),
                "best_for": [str(x) for x in (item.get("best_for") or [])],
            }
        )
    return tuple(out)


def reload_templates() -> None:
    """测试或热更新时清空缓存。"""
    _load_templates.cache_clear()


def get_template(style_id: str) -> PromptStyleTemplate | None:
    for tpl in _load_templates():
        if tpl["id"] == style_id:
            return tpl
    return None


def list_templates() -> list[dict]:
    return [dict(t) for t in _load_templates()]

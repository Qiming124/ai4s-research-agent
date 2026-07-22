# =============================================================================
# 理论侧 HTTP API（工作区文件 / 假设 DAG 已下线）。
#
# 符号与假设仍由 data/theory 种子经 theory_workspace 注入 Agent 提示词；
# 不再对外暴露 /v1/theory/workspace* 与 /v1/theory/assumption-dag*。
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["theory"])

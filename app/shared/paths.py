# 项目目录布局常量（重构后统一从此模块解析路径）。

from __future__ import annotations

from pathlib import Path

# app/shared/paths.py → 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"
CONF_ROOT = PROJECT_ROOT / "conf"
DOC_ROOT = PROJECT_ROOT / "doc"
LOG_ROOT = PROJECT_ROOT / "log"
DATA_ROOT = PROJECT_ROOT / "data"


def resolve_env_file() -> Path:
    """
    解析运行时 .env 路径：优先 conf/.env，其次仓库根 .env（兼容旧布局）。

    返回:
        存在的 .env 文件路径；若均不存在则返回 conf/.env 作为默认目标
    """
    for candidate in (CONF_ROOT / ".env", PROJECT_ROOT / ".env"):
        if candidate.is_file():
            return candidate
    return CONF_ROOT / ".env"


def conf_path(name: str) -> Path:
    """返回 conf/ 下配置文件绝对路径。"""
    return CONF_ROOT / name

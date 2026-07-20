# =============================================================================
# PDF 导出用 CJK 字体解析与下载。
#
# 职责：
#     1. resolve_cjk_font_path() 按 bundled → cache → system → download 顺序查找
#     2. 缓存 NotoSansSC 到 data/fonts/
#     3. 供 pandoc xelatex 与 reportlab 注册字体
#
# 架构位置：
#     - 被调用：server/export/pdf_exporter.py、html_pdf_renderer.py
#     - 调用：urllib 下载、Path 文件系统
#
# 阅读提示：
#     - 新人先看 resolve_cjk_font_path
#
# Debug：
#     - 字体下载失败 → 网络或 _DOWNLOAD_URL 不可达
#     - 仍乱码 → 系统字体路径未列入 _SYSTEM_FONT_CANDIDATES
# =============================================================================

from __future__ import annotations

import logging
import shutil
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_BUNDLED_FONTS = [
    Path(__file__).resolve().parent / "fonts" / "NotoSansCJKsc-Regular.otf",
    Path(__file__).resolve().parent / "fonts" / "NotoSansSC-Regular.otf",
]
_CACHE_FONT = Path(__file__).resolve().parents[3] / "data" / "fonts" / "NotoSansSC-Regular.otf"
_DOWNLOAD_URL = (
    "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
)

_SYSTEM_FONT_CANDIDATES = [
    Path("/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf"),
    Path("/usr/share/fonts/google-noto/NotoSansSC-Regular.otf"),
    Path("/usr/share/fonts/noto-cjk/NotoSansSC-Regular.otf"),
]


def resolve_cjk_font_path() -> Path | None:
    """返回可用于 fpdf2 的简体中文 OpenType 字体路径。"""
    for candidate in (*_BUNDLED_FONTS, _CACHE_FONT, *_SYSTEM_FONT_CANDIDATES):
        if candidate.is_file() and candidate.stat().st_size > 100_000:
            return candidate
    try:
        return _download_font_cache()
    except OSError as exc:
        logger.warning("下载 CJK 字体失败: %s", exc)
        return None


def _download_font_cache() -> Path:
    _CACHE_FONT.parent.mkdir(parents=True, exist_ok=True)
    logger.info("正在下载 PDF 中文字体到 %s", _CACHE_FONT)
    urllib.request.urlretrieve(_DOWNLOAD_URL, _CACHE_FONT)
    if not _CACHE_FONT.is_file() or _CACHE_FONT.stat().st_size < 100_000:
        raise OSError("下载的字体文件无效")
    return _CACHE_FONT


def copy_bundled_font_to_cache_if_needed() -> None:
    """Docker/离线环境优先使用打包字体。"""
    bundled = next((p for p in _BUNDLED_FONTS if p.is_file()), None)
    if bundled and (
        not _CACHE_FONT.is_file() or _CACHE_FONT.stat().st_size < bundled.stat().st_size
    ):
        _CACHE_FONT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, _CACHE_FONT)

# 文档分块：按字符窗口切分文本/markdown。

from __future__ import annotations


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """将文本切分为重叠字符块。"""
    normalized = text.strip()
    if not normalized:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap 不能为负")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    length = len(normalized)
    step = chunk_size - chunk_overlap

    while start < length:
        end = min(start + chunk_size, length)
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start += step

    return chunks

# MCP Server：RAG 按需检索（封装 L3 向量库）。

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag")


def _retrieve(query: str, top_k: int) -> str:
    from server.config import get_settings
    from server.memory.rag.retrieval import retrieve_for_query

    settings = get_settings()
    if not settings.enable_rag:
        return json.dumps(
            {"error": "RAG 未启用。请在 conf/.env 中设置 ENABLE_RAG=true"},
            ensure_ascii=False,
        )

    snippets = retrieve_for_query(query, settings, top_k=top_k)
    return json.dumps(
        {
            "query": query,
            "count": len(snippets),
            "results": [
                {
                    "doc_id": s.doc_id,
                    "title": s.title,
                    "source": s.source,
                    "content": s.content,
                    "score": s.score,
                }
                for s in snippets
            ],
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def retrieve(query: str, top_k: int = 4) -> str:
    """从本地 RAG 向量库检索与 query 相关的文档片段。

    Args:
        query: 检索问题或关键词
        top_k: 返回片段数量（默认 4）
    """
    return _retrieve(query, top_k)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

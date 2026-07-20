# =============================================================================
# MCP Server：RAG 按需检索（按 session_id 隔离）。
#
# 职责：
#     1. rag_retrieve 工具：检查 ENABLE_RAG 后调用 retrieve_for_query
#     2. 要求非空 session_id，返回 JSON 片段列表
#     3. 供 Agent 在对话中主动检索课题知识库
#
# 架构位置：
#     - 被调用：MCP Client stdio 子进程
#     - 调用：server/memory/rag/retrieval.py、server/config.py
#
# 阅读提示：
#     - 新人先看 _retrieve 与 rag_retrieve 工具定义
#
# Debug：
#     - error RAG 未启用 → ENABLE_RAG=false
#     - 空 session_id → 工具参数校验拒绝
# =============================================================================

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag")


def _retrieve(query: str, top_k: int, session_id: str) -> str:
    from server.config import get_settings
    from server.memory.rag.retrieval import retrieve_for_query

    settings = get_settings()
    if not settings.enable_rag:
        return json.dumps(
            {"error": "RAG 未启用。请在 conf/.env 中设置 ENABLE_RAG=true"},
            ensure_ascii=False,
        )

    session_id = session_id.strip()
    if not session_id:
        return json.dumps(
            {
                "error": "缺少 session_id。rag__retrieve 需要会话 ID 以隔离检索范围。",
            },
            ensure_ascii=False,
        )

    snippets = retrieve_for_query(
        query,
        settings,
        session_id=session_id,
        top_k=top_k,
    )
    return json.dumps(
        {
            "query": query,
            "session_id": session_id,
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
async def retrieve(query: str, top_k: int = 4, session_id: str = "") -> str:
    """从**当前会话** RAG 向量库检索与 query 相关的文档片段。

    Args:
        query: 检索问题或关键词
        top_k: 返回片段数量（默认 4）
        session_id: 会话 ID（必填，仅检索该会话上传/索引的文档）
    """
    return _retrieve(query, top_k, session_id)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
